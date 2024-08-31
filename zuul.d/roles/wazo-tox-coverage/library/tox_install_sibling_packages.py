#!/usr/bin/python

# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

# origin: https://opendev.org/zuul/zuul-jobs/src/branch/master/roles/tox/library/tox_install_sibling_packages.py  # noqa
# It is unpachted, except for black and linter


try:
    import configparser
except ImportError:
    import ConfigParser as configparser

import ast
import os
import subprocess
import tempfile
import traceback

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = '''
---
module: tox_install_sibling_packages
short_description: Install packages needed by tox that have local git versions
author: Monty Taylor (@mordred)
description:
  - Looks for git repositories that zuul has placed on the system that provide
    python packages needed by package tox is testing. If if finds any, it will
    install them into the tox virtualenv so that subsequent runs of tox will
    use the provided git versions.
requirements:
  - "python >= 3.5"
options:
  tox_show_config:
    description:
      - Path to a file containing the output from C(tox --showconfig).
    required: true
    type: path
  project_dir:
    description:
      - The directory in which the project we care about is in.
    required: true
    type: str
  projects:
    description:
      - A list of project dicts that zuul knows about
    required: true
    type: list
'''

log = list()


def to_filename(name):
    """Convert a project or version name to its filename-escaped form
    Any '-' characters are currently replaced with '_'.

    Implementation vendored from pkg_resources.to_filename in order to avoid
    adding an extra runtime dependency.
    """
    return name.replace('-', '_')


def get_sibling_python_packages(projects, tox_python):
    '''Finds all python packages that zuul has cloned.

    If someone does a require_project: and then runs a tox job, it can be
    assumed that what they want to do is to test the two together.
    '''
    packages = {}

    for project in projects:
        root = project['src_dir']
        package_name = None
        setup_cfg = os.path.join(root, 'setup.cfg')
        found_python = False
        if os.path.exists(setup_cfg):
            found_python = True
            c = configparser.ConfigParser()
            c.read(setup_cfg)
            try:
                package_name = c.get('metadata', 'name')
                packages[package_name] = root
            except Exception:
                # Some things have a setup.cfg, but don't keep
                # metadata in it; fall back to setup.py below
                log.append("[metadata] name not found in %s, skipping" % setup_cfg)
        if not package_name and os.path.exists(os.path.join(root, 'setup.py')):
            found_python = True
            # It's a python package but doesn't use pbr, so we need to run
            # python setup.py --name to get setup.py to tell us what the
            # package name is.
            package_name = subprocess.check_output(
                [os.path.abspath(tox_python), 'setup.py', '--name'],
                cwd=os.path.abspath(root),
                stderr=subprocess.STDOUT,
            ).decode('utf-8')
            if package_name:
                package_name = package_name.strip()
                packages[package_name] = root
        if found_python and not package_name:
            log.append(f"Could not find package name for {root}")
    return packages


def get_installed_packages(tox_python):
    # We use the output of pip freeze here as that is pip's stable public
    # interface.
    frozen_pkgs = subprocess.check_output(
        [tox_python, '-m', 'pip', '-qqq', 'freeze'], stderr=subprocess.STDOUT
    ).decode('utf-8')
    # Matches strings of the form:
    # 1. '<package_name>==<version>'
    # 2. '# Editable Git install with no remote (<package_name>==<version>)'
    # 3. '<package_name> @ <URI_reference>' # PEP440, PEP508, PEP610
    # results <package_name>
    installed_packages = []
    for x in frozen_pkgs.split('\n'):
        if '==' in x:
            installed_packages.append(x[x.find('(') + 1 :].split('==')[0])
        elif '@' in x:
            installed_packages.append(x.split('@')[0].rstrip(' \t'))
    return installed_packages


def write_new_constraints_file(constraints, packages):
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as constraints_file:
        constraints_lines = open(constraints).read().split('\n')
        for line in constraints_lines:
            package_name = line.split('===')[0]
            if package_name in packages:
                continue
            constraints_file.write(line)
            constraints_file.write('\n')
        return constraints_file.name


def _get_package_root(name, sibling_packages):
    '''
    Returns a package root from the sibling packages dict.

    If name is not found in sibling_packages, tries again using the 'filename'
    form of the name returned by the setuptools package resource API.

    :param name: package name
    :param sibling_packages: dict of python packages that zuul has cloned
    :returns: the package root (str)
    :raises: KeyError
    '''
    try:
        pkg_root = sibling_packages[name]
    except KeyError:
        pkg_root = sibling_packages[to_filename(name)]

    return pkg_root


def find_installed_siblings(tox_python, package_name, sibling_python_packages):
    installed_sibling_packages = []
    for dep_name in get_installed_packages(tox_python):
        log.append(f"Found {dep_name} python package installed")
        if dep_name == package_name or to_filename(dep_name) == package_name:
            # We don't need to re-process ourself.
            # We've filtered ourselves from the source dir list,
            # but let's be sure nothing is weird.
            log.append(f"Skipping {dep_name} because it's us")
            continue
        if dep_name in sibling_python_packages:
            log.append(
                "Package {name} on system in {root}".format(
                    name=dep_name, root=sibling_python_packages[dep_name]
                )
            )
            installed_sibling_packages.append(dep_name)
        elif to_filename(dep_name) in sibling_python_packages:
            real_name = to_filename(dep_name)
            log.append(
                "Package {name} ({pkg_name}) on system in {root}".format(
                    name=dep_name,
                    pkg_name=real_name,
                    root=sibling_python_packages[real_name],
                )
            )
            # need to use dep_name here for later constraint file rewrite
            installed_sibling_packages.append(dep_name)
    return installed_sibling_packages


def install_siblings(envdir, projects, package_name, constraints):
    changed = False
    tox_python = f'{envdir}/bin/python'

    sibling_python_packages = get_sibling_python_packages(projects, tox_python)
    for name, root in sibling_python_packages.items():
        log.append(f"Sibling {name} at {root}")

    installed_sibling_packages = find_installed_siblings(
        tox_python, package_name, sibling_python_packages
    )

    if constraints:
        constraints_file = write_new_constraints_file(
            constraints, installed_sibling_packages
        )

    for sibling_package in installed_sibling_packages:
        changed = True
        log.append(f"Uninstalling {sibling_package}")
        uninstall_output = subprocess.check_output(
            [tox_python, '-m', 'pip', 'uninstall', '-y', sibling_package],
            stderr=subprocess.STDOUT,
        )
        log.extend(uninstall_output.decode('utf-8').split('\n'))

        args = [tox_python, '-m', 'pip', 'install']
        if constraints:
            args.extend(['-c', constraints_file])

        pkg_root = _get_package_root(sibling_package, sibling_python_packages)
        log.append(
            "Installing {name} from {root} for deps".format(
                name=sibling_package, root=pkg_root
            )
        )
        args.append(pkg_root)

        install_output = subprocess.check_output(args)
        log.extend(install_output.decode('utf-8').split('\n'))

    for sibling_package in installed_sibling_packages:
        changed = True
        pkg_root = _get_package_root(sibling_package, sibling_python_packages)
        log.append(f"Installing {sibling_package} from {pkg_root}")

        install_output = subprocess.check_output(
            [tox_python, '-m', 'pip', 'install', '--no-deps', pkg_root]
        )
        log.extend(install_output.decode('utf-8').split('\n'))
    return changed


def get_envlist(tox_config):
    envlist = []
    if 'tox' in tox_config.sections():
        envlist_default = ast.literal_eval(tox_config.get('tox', 'envlist_default'))
        tox_args = ast.literal_eval(tox_config.get('tox', 'args'))
        if 'ALL' in tox_args or not envlist_default:
            for section in tox_config.sections():
                if section.startswith('testenv'):
                    envlist.append(section.split(':')[1])
        else:
            for testenv in envlist_default:
                envlist.append(testenv)
    else:
        for section in tox_config.sections():
            envlist.append(section.split(':')[1])
    return envlist


def main():
    module = AnsibleModule(
        argument_spec=dict(
            tox_show_config=dict(required=True, type='path'),
            tox_constraints_file=dict(type='str'),
            tox_package_name=dict(type='str'),
            project_dir=dict(required=True, type='str'),
            projects=dict(required=True, type='list'),
        )
    )
    constraints = module.params.get('tox_constraints_file')
    tox_package_name = module.params.get('tox_package_name')
    project_dir = module.params['project_dir']
    projects = module.params['projects']
    tox_show_config = module.params.get('tox_show_config')

    tox_config = configparser.RawConfigParser()
    tox_config.read(tox_show_config)

    envlist = get_envlist(tox_config)

    if not envlist:
        module.exit_json(changed=False, msg='No envlist to run, no action needed.')

    log.append(f'Using envlist: {envlist}')

    if not tox_package_name and not os.path.exists(
        os.path.join(project_dir, 'setup.cfg')
    ):
        module.exit_json(changed=False, msg="No setup.cfg, no action needed")
    if constraints and not os.path.exists(constraints):
        module.fail_json(msg="Constraints file {constraints} was not found")

    # Who are we?
    package_name = tox_package_name
    if not package_name:
        try:
            c = configparser.ConfigParser()
            c.read(os.path.join(project_dir, 'setup.cfg'))
            package_name = c.get('metadata', 'name')
        except Exception:
            module.exit_json(
                changed=False, msg="No name in setup.cfg, skipping siblings"
            )

    log.append(
        "Processing siblings for {name} from {project_dir}".format(
            name=package_name, project_dir=project_dir
        )
    )

    changed = False
    for testenv in envlist:
        env_dir = tox_config.get(f"testenv:{testenv}", 'env_dir')
        env_log_dir = tox_config.get(f"testenv:{testenv}", 'env_log_dir')
        try:
            # Write a log file into the .tox dir so that it'll get picked up
            # Name it with testenv as a prefix so that fetch-tox-output
            # will properly get it in a multi-env scenario
            log_file = '{env_log_dir}/{test_env}-siblings.txt'.format(
                env_log_dir=env_log_dir, test_env=testenv
            )
            changed = changed or install_siblings(
                env_dir, projects, package_name, constraints
            )
        except subprocess.CalledProcessError as e:
            tb = traceback.format_exc()
            log.append(str(e))
            log.append(tb)
            log.append("Output:")
            log.extend(e.output.decode('utf-8').split('\n'))
            module.fail_json(msg=str(e), log="\n".join(log))
        except Exception as e:
            tb = traceback.format_exc()
            log.append(str(e))
            log.append(tb)
            module.fail_json(msg=str(e), log="\n".join(log))
        finally:
            log_text = "\n".join(log)
            module.append_to_file(log_file, log_text)
    module.exit_json(changed=changed, msg=log_text)


if __name__ == '__main__':
    main()
