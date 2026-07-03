# wazo-calld ARI load tests

A Locust harness against the `real_asterisk` (chan-test) integration stack. It
supports two related validations, both driven by the same owned-channel pool:

1. **`/users/me/calls` ARI-request / latency A/B** — validates the snapshot
   optimization (`calls: read channel variables from ARI snapshots on the
   listing path`): the endpoint now reads channel variables from the snapshot's
   `channelvars` dict instead of issuing one `getChannelVar` HTTP call per
   variable per call. This is the primary use below.
2. **ARI connection-pool exhaustion** reproduction (the harness's original
   purpose) — see *Pool-exhaustion reproduction* near the end.

## What the optimization changes, and the A/B toggle

`GET /users/me/calls` lists the token user's channels: one `channels.list()`,
then `make_call_from_channel` per matching call. Before the optimization each
call issued ~9 blocking `getChannelVar` round-trips (plus repeated
`bridges.list`); after it, the whole request is a flat `channels.list` +
`bridges.list` — **the per-call ARI round-trips are gone** when the variables it
needs are embedded in channel snapshots.

Snapshots only embed a variable if it is in `ari.conf`'s `channelvars`.
`Channel._get_var` falls back to a live `getChannelVar` for anything missing. So
the optimization is toggled **on the same calld build, purely via `ari.conf`**:

| `--ari-conf` | `channelvars` list | listing behaviour |
|--------------|--------------------|-------------------|
| `optimized` (default) | repo `assets/etc/asterisk/ari.conf` (extended) | snapshot reads, ~0 per-call `getChannelVar` |
| `baseline` | `load_tests/ari.conf.baseline` (wazo-26.02 list) | falls back to ~9 live `getChannelVar` per call |

`ari.conf.baseline` is the pre-optimization list; it is **not** an empty list
(that config never shipped). This is the real before/after this change deploys.

## Prerequisites

- Docker + docker compose.
- A `chan-test` clone (default `~/wazo/chan-test`, or set `CHAN_TEST_DIR`).
- A virtualenv with the load-test deps:

  ```bash
  python3 -m venv .venv && . .venv/bin/activate
  pip install -r requirements.txt
  ```

Loopback docker ports are used, so on a restricted shell these runs need the
sandbox disabled.

## Latency A/B: `GET /users/me/calls`

`run.sh` brings up the stack (reading the selected `ari.conf`), discovers mapped
host ports, programs a mock user token, originates `CHANNEL_COUNT` channels
owned by that user, and launches Locust. Each stack bring-up reads `ari.conf`
fresh, so the two configs are two independent runs.

Isolate the read path with Locust's built-in user-class selection — pass
`CallsReader` as a positional arg so the `DialMobileFlooder` (pool-exhaustion
noise) does not run. Freeze the channel pool at `M` with `CHANNEL_CAP=M` so the
number of listed calls is a fixed independent variable (otherwise the keeper
grows it mid-run).

### Primary — per-request latency vs number of owned calls (concurrency 1)

The intrinsic effect is a per-request property; measure it at one user so GIL
contention is not a confound. Sweep `M`, run each config:

```bash
for M in 1 10 50 100; do
  CHANNEL_COUNT=$M CHANNEL_CAP=$M ARI_LATENCY_MS=20 \
    ./run.sh --ari-conf baseline  -- --headless -u 1 -r 1 -t 60s CallsReader --csv="base_M$M"
  CHANNEL_COUNT=$M CHANNEL_CAP=$M ARI_LATENCY_MS=20 \
    ./run.sh --ari-conf optimized -- --headless -u 1 -r 1 -t 60s CallsReader --csv="opt_M$M"
done
```

Locust writes `*_stats.csv` with median / p95 / p99 for the `users/me/calls`
entry. Expected: **baseline median rises steeply with M** (≈ `M × 9 ×
ARI_round_trip`), **optimized stays shallow and near-flat**. `ARI_LATENCY_MS`
(netem, see below) amplifies each baseline round-trip so the difference is
legible even at one user; keep it identical across the two configs.

### Secondary — concurrency ramp at fixed M

Answers "how much load before the knee". Ramp users at a fixed pool:

```bash
CHANNEL_COUNT=50 CHANNEL_CAP=50 ./run.sh --ari-conf optimized -- --headless -u 40 -r 10 -t 2m CallsReader --csv=opt_ramp
CHANNEL_COUNT=50 CHANNEL_CAP=50 ./run.sh --ari-conf baseline  -- --headless -u 40 -r 10 -t 2m CallsReader --csv=base_ramp
```

Expected: optimized sustains higher RPS / lower p95 before saturating. This
regime is CPU/GIL-bound (see *Why raw load is not enough*), so treat it as
directional, not a clean isolation of the endpoint cost.

### Known limitation

The harness parks owned channels in Stasis unbridged, so `bridges.list()` is
empty, `talking_to` is `{}`, and the one connected-channel `user()` read per
call is not exercised. Baseline cost is therefore slightly *undercounted* — the
real gap is a touch larger than measured.

## Manual method: count ARI requests from Asterisk logs

For a deterministic check (or on a real Wazo stack, no Locust), count the ARI
requests one `/users/me/calls` triggers, using Asterisk's own request logging.
This measures ARI *request count* — the thing the optimization changes directly
— rather than latency.

1. **Enable ARI request logging** in Asterisk (globally, all applications):

   ```bash
   # load-test stack:
   docker compose -p calld-loadtest \
     -f docker-compose.yml -f docker-compose.real_asterisk.override.yml \
     -f docker-compose.load_test.override.yml exec ari asterisk -rx "ari set debug all on"
   # real Wazo stack:
   asterisk -rx "ari set debug all on"
   ```

   `res_ari` then logs, per request, via `ast_verbose`:
   `<--- ARI request received from: … --->` followed by `<METHOD> <uri>`. Ensure
   `logger.conf` captures `verbose` (the test asset's `console = *` does; a real
   Wazo stack's `/var/log/asterisk/full` includes it — else `core set verbose 3`).

2. **Quiesce** the stack (no flooder, a small fixed set of owned calls, no other
   traffic) so the burst from your request stands out.

3. **Issue exactly one** `GET /users/me/calls` and **count the per-variable
   reads** in the window:

   ```bash
   # load-test stack — count GET .../variable lines emitted by ARI:
   docker compose -p calld-loadtest -f docker-compose.yml \
     -f docker-compose.real_asterisk.override.yml \
     -f docker-compose.load_test.override.yml logs --since 10s ari \
     | grep -c 'GET /ari/channels/.*/variable'

   # real Wazo stack:
   grep 'GET .*channels/.*/variable' /var/log/asterisk/full | wc -l
   ```

   Expected: **baseline ≈ M × 9** `.../variable` GETs; **optimized ≈ 0**, leaving
   only `GET /ari/channels` + `GET /ari/bridges`.

4. **A/B the config.** On the load-test stack, restart with `--ari-conf
   baseline` vs `optimized`. On a real stack, edit the `channelvars` line in
   `/etc/asterisk/ari.conf` and `asterisk -rx "module reload res_ari.so"` (or
   restart Asterisk) between the two counts.

Corroborating signal under load (either method): baseline produces far more
`Connection pool is full, discarding connection: ari` warnings in the wazo-calld
log for the same offered load.

## Pool-exhaustion reproduction (original purpose)

wazo-calld makes every ARI call through one process-wide `requests.Session`
(`pool_maxsize=10`, `pool_block=False`) shared by all HTTP- and event-handler
threads. Running both user classes pushes >10 ARI requests in flight:

- **`CallsReader`** — spams `GET /users/me/calls`; pressures but (HTTP server
  `max_threads=10`) cannot alone exceed the pool.
- **`DialMobileFlooder`** — publishes synthetic `dial` StasisStart events; each
  makes `dial_mobile` spawn an unbounded `_PollingContactDialer` thread polling
  ARI ~8×/s. This is the lever that crosses 10.

Because `pool_block=False`, exhaustion shows up not as hangs but as
`urllib3 … Connection pool is full, discarding connection: ari. Connection pool
size: 10` in the wazo-calld log, plus rising `users/me/calls` response times.

```bash
# build once, then a 2-minute headless ramp with both user classes:
./run.sh --build -- --headless -u 40 -r 10 -t 2m
# watch, in another shell:
cd ../assets && docker compose -p calld-loadtest \
  -f docker-compose.yml -f docker-compose.real_asterisk.override.yml \
  -f docker-compose.load_test.override.yml logs -f calld | grep -i 'connection pool is full'
```

### Why raw load is not enough — and the latency knob that forces it

On this stack, load alone cannot reproduce the warning: wazo-calld is
**CPU/GIL-bound** (~1 core under load), which mechanically pins concurrent
in-flight ARI at `ari_call_latency / cpu_per_call ≈ 10 ms / 1.7 ms ≈ 6` — below
the pool size of 10, regardless of throughput levers. The only thing that raises
concurrency is per-call **I/O latency** without added CPU, so the load-test
override injects ~20 ms on Asterisk's ARI egress with `tc`/`netem` (`ari-netem`
sidecar; `ARI_LATENCY_MS`, default 20, `0` disables). Effective ~40 ms per call
lifts concurrency to ~20+ and reproduces the warning (~1000 warnings and
`users/me/calls` hitting the 10 s Locust timeout in a ~100 s run). This **forces**
the condition to validate a fix; it is not organic production load. The bug is
independently proven by 16,640 such warnings in the Adista/Cultura production log
(2026-06-15).

## Knobs

| Env / arg | Meaning | Default |
|-----------|---------|---------|
| `--ari-conf` | `optimized` (extended `channelvars`) or `baseline` (wazo-26.02 list) | `optimized` |
| Locust positional (e.g. `CallsReader`) | Restrict to given user class(es) | both run |
| `CHANNEL_COUNT` | Owned channels created at setup (listing amplification factor) | 20 |
| `CHANNEL_CAP` | Max owned channels the keeper grows to; set `== CHANNEL_COUNT` to freeze the pool for a latency run | 200 |
| `CHANNEL_GROWTH_STEP` | Channels added per growth interval | 15 |
| `CHANNEL_GROWTH_INTERVAL` | Seconds between growth steps | 5 |
| `CHANNEL_KEEPER_INTERVAL` | Keeper reconcile period (prune + replenish) | 2 |
| `CHANNEL_KEEPER_BATCH` | Max channels originated per keeper iteration | 25 |
| `ARI_LATENCY_MS` | netem delay on Asterisk ARI egress (`0` disables) | 20 |
| `DIAL_AOR` | AOR used in dial events (must match `pjsip.conf` endpoint) | `load-test-aor` |
| `CHAN_TEST_DIR` | Path to the chan-test clone | `~/wazo/chan-test` |

## Files

- `locustfile.py` — `CallsReader` (GET /users/me/calls) + `DialMobileFlooder`.
- `harness.py` — mock auth token + owned-channel pool + the `_ChannelKeeper`
  (prune/replenish/grow) thread.
- `dial_events.py` — synthetic `dial` StasisStart publisher (`wazo-bus`).
- `ari.conf.baseline` — pre-optimization `channelvars` list for the A/B toggle.
- `run.sh` — stack lifecycle, `--ari-conf` selection, Locust launch.
- `../assets/etc/asterisk/pjsip.conf` — `load-test-aor` endpoint/AOR (see below).
- `../assets/docker-compose.load_test.override.yml` — load-test-only override
  (the regular suite is unaffected): selectable `ari.conf` mount, `pjsip.conf`
  mount, and the `ari-netem` latency sidecar (`network_mode: service:ari`,
  `cap_add: NET_ADMIN`, installs `iproute2`, applies `tc … netem delay`).

## The PICKUPMARK / PJSIP_ENDPOINT requirement

Only relevant to `DialMobileFlooder`. `dial_all_contacts` reads
`getChannelVar(PJSIP_ENDPOINT(<aor>,PICKUPMARK))` unguarded; on Asterisk 22
`PICKUPMARK` is not a native `PJSIP_ENDPOINT` field, so with no matching endpoint
the read returns HTTP 500 and kills the StasisStart handler before any
`_PollingContactDialer` is created. `pjsip.conf` therefore defines a
`load-test-aor` endpoint exposing `PICKUPMARK` via `set_var`, with a
contact-less AOR (so `PJSIP_DIAL_CONTACTS(load-test-aor)` is empty and the dialer
polls without originating contacts). `DIAL_AOR` must equal the endpoint name.
