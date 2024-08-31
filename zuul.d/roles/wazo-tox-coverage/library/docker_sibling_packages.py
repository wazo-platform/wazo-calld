#!/usr/bin/env python3

import glob
import os
import subprocess

import yaml
from ansible.module_utils.basic import AnsibleModule


def get_package_name(tox_python, root):
    subprocess.check_output(
        [os.path.abspath(tox_python), 'setup.py', 'egg_info'], cwd=os.path.abspath(root)
    )
    top_level = glob.glob(f"{root}/*.egg-info/top_level.txt")[0]
    with open(top_level) as f:
        return f.readline().strip()


def main():
    module = AnsibleModule(
        argument_spec={
            'services': {'required': True, 'type': 'list'},
            'tox_envlist': {'required': True, 'type': 'str'},
            'project_dir': {'required': True, 'type': 'str'},
            'projects': {'required': True, 'type': 'list'},
        }
    )
    envlist = module.params['tox_envlist']
    project_dir = module.params['project_dir']
    projects = module.params['projects']
    services = module.params['services']

    envdir = f'{project_dir}/.tox/{envlist}'
    if not os.path.exists(envdir):
        module.exit_json(
            changed=False,
            msg="envdir does not exist, skipping docker compose customisation",
        )
    tox_python = f'{envdir}/bin/python'

    if not services:
        package_name = get_package_name(tox_python, project_dir)
        if package_name.startswith("wazo_"):
            package_name = package_name[5:]
        services = [package_name]

    volumes = set()
    for project in projects:
        root = project['src_dir']

        if root == project_dir:
            continue
        elif not os.path.exists(os.path.join(root, 'setup.py')):
            continue

        package = get_package_name(tox_python, root)
        volumes.add(
            f"{os.path.realpath(root)}/{package}:/opt/venv/lib/python3.9/site-packages/{package}"
        )

    volumes = list(volumes)
    docker_compose_override = {
        'services': {service: {'volumes': volumes} for service in services}
    }

    docker_compose_override_contents = yaml.dump(docker_compose_override)
    docker_compose_override_file = (
        f"{project_dir}/docker-compose.integration.override.yaml"
    )

    with open(docker_compose_override_file, "w") as f:
        f.write(docker_compose_override_contents)

    module.exit_json(
        file=os.path.realpath(docker_compose_override_file),
        contents=docker_compose_override_contents,
    )


if __name__ == '__main__':
    main()
