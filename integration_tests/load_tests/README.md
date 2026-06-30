# ARI connection-pool exhaustion load test

Reproduces exhaustion of wazo-calld's **single, process-wide ARI
`requests.Session`** connection pool.

## Mechanism

wazo-calld makes every outbound ARI REST call through one
`swaggerpy.http_client.SynchronousHttpClient` → one `requests.Session` with the
default adapter (`pool_maxsize=10`, **`pool_block=False`**). This pool is shared
by *all* request-handler threads and *all* bus/stasis event-handler threads.

Two load sources run concurrently and together push more than 10 ARI requests
in flight at once:

1. **`CallsReader`** — spams `GET /users/me/calls` through `wazo-calld-client`.
   Each request amplifies into many sequential ARI calls: `channels.list()` plus
   ~5 uncached ARI calls per channel **owned by the token's user**
   (`make_call_from_channel`: 2×`bridges.list` + 3 uncached `getChannelVar`).
   The HTTP server has only `max_threads=10`, so this path alone tops out *at*
   the pool size — it pressures but cannot exceed it.
2. **`DialMobileFlooder`** — publishes synthetic `dial` StasisStart events to
   RabbitMQ. Each event makes `dial_mobile` spawn an **unbounded**
   `_PollingContactDialer` thread that polls ARI ~8×/s. This is the lever that
   pushes total in-flight ARI calls past 10.

Because `pool_block=False`, exhaustion does **not** appear as hangs. urllib3
opens an extra connection, uses it, and discards it on release, logging:

```
urllib3.connectionpool WARNING Connection pool is full, discarding connection: ari. Connection pool size: 10
```

**Intended pass signal** = that warning in the wazo-calld logs **and** rising
`users/me/calls` response times in Locust as load ramps.

### Why raw load is not enough — and the latency knob that forces it

On the bundled `real_asterisk` (chan-test) stack, **load alone cannot reproduce
the warning**: wazo-calld is **CPU/GIL-bound** (one process, pegged at ~1 core
under load). With one core maxed, concurrent in-flight ARI is *mechanically
pinned*:

```
concurrency ≈ ari_call_latency / cpu_per_call ≈ 10 ms / 1.7 ms ≈ 6
```

So it plateaus at **~5–6 concurrent**, never reaching the pool size of 10 —
regardless of how many bus events, stasis invocations, or `/users/me/calls`
requests you throw at it. Those are all *throughput* levers; in a CPU-pinned
regime throughput is already maxed, so they only queue work. (Confirmed across
empty-AOR, 200-channel, and real-contact-bridging variants — all ~6.)

The **only** thing that raises concurrency is per-call **I/O latency** without
adding CPU. The load-test override therefore injects ~20 ms on Asterisk's ARI
egress with `tc`/`netem` (`ari-netem` sidecar; `ARI_LATENCY_MS`, default 20,
`0` disables). Effective per-call latency becomes ~40 ms (netem delays each
egress packet), which lifts concurrency to ~20+ and **reproduces the warning**:

- peak **~23 concurrent** calld→ARI connections,
- **~1000 `Connection pool is full, discarding connection: ari. Connection pool
  size: 10`** warnings in a ~100 s run, and
- `users/me/calls` rising to the 10 s Locust timeout.

This **forces** the condition to validate a fix; it is **not** an organic
reproduction of production load. The bug is independently proven by **16,640**
such warnings in the Adista/Cultura production log (2026-06-15). Why production
crosses 10 *organically* is a hypothesis — most likely real Asterisk ARI calls
are slower under real load (busy server, large `channels.list`/`bridges.list`
payloads), giving the same held-connection effect netem injects here. The prod
log has no ARI-latency data to confirm this.

## Why real channels

The harness originates a pool of **real** chan-test channels (kept Up, owned by
the token's user) before the run. Real channels are required because:

- `GET /users/me/calls` only amplifies when `channels.list()` returns owned
  channels, and
- each `_PollingContactDialer._run` first calls `channels.get(channel_id)`; on a
  non-existent (synthetic) channel it raises `ARINotFound`, the thread dies, and
  no sustained load is produced. Referencing real channel ids keeps the polling
  threads alive.

## Prerequisites

- Docker + docker compose.
- A `chan-test` clone (default `~/wazo/chan-test`, or set `CHAN_TEST_DIR`).
- A virtualenv with the load-test deps:

  ```bash
  python3 -m venv .venv && . .venv/bin/activate
  pip install -r requirements.txt
  ```

## Run

```bash
# First time: build images, then run a 2-minute headless test
./run.sh --build -- --headless -u 40 -r 10 -t 2m

# Subsequent runs (images already built), interactive Locust web UI
./run.sh
```

`run.sh` brings up the `real_asterisk` asset, discovers the mapped host ports,
exports them, and launches Locust against wazo-calld. It tears the stack down on
exit unless `--keep-up` is given.

In another shell, watch for exhaustion:

```bash
cd ../assets
docker compose -p calld-loadtest \
  -f docker-compose.yml -f docker-compose.real_asterisk.override.yml \
  -f docker-compose.load_test.override.yml \
  logs -f calld | grep -i 'connection pool is full'
```

## Knobs

| Env / arg | Meaning | Default |
|-----------|---------|---------|
| `CHANNEL_COUNT` | Owned channels created at setup (HTTP amplification factor) | 20 |
| `CHANNEL_CAP` | Max owned channels the keeper grows the pool to | 200 |
| `CHANNEL_GROWTH_STEP` | Channels added per growth interval | 15 |
| `CHANNEL_GROWTH_INTERVAL` | Seconds between growth steps | 5 |
| `CHANNEL_KEEPER_INTERVAL` | Keeper reconcile period (prune + replenish) | 2 |
| `CHANNEL_KEEPER_BATCH` | Max channels originated per keeper iteration | 25 |
| Locust `-u` | Total users; ratio is 10 `CallsReader` : 1 `DialMobileFlooder` | — |
| `DialMobileFlooder` `wait_time` | Dialer-thread accrual rate (in `locustfile.py`) | 0.2–0.5s |
| `DIAL_AOR` | AOR used in the dial events (must match `pjsip.conf` endpoint) | `load-test-aor` |
| `ARI_LATENCY_MS` | netem delay injected on Asterisk ARI egress (`0` disables) | 20 |
| `CHAN_TEST_DIR` | Path to the chan-test clone | `~/wazo/chan-test` |

The keeper keeps the owned pool alive (prunes ids whose channel is gone,
replenishes) and grows it to `CHANNEL_CAP` — this sustains polling dialers and
pressures the `/users/me/calls` HTTP side. `ARI_LATENCY_MS` is what actually
pushes concurrency past the pool size (see *Why raw load is not enough*); without
it the run plateaus at ~6 concurrent and never warns.

## Files

- `locustfile.py` — `CallsReader` + `DialMobileFlooder` users.
- `harness.py` — mock auth token + owned-channel pool + the `_ChannelKeeper`
  (prune/replenish/grow) thread.
- `dial_events.py` — synthetic `dial` StasisStart publisher (`wazo-bus`).
- `run.sh` — stack lifecycle + Locust launch.
- `../assets/etc/asterisk/pjsip.conf` — `load-test-aor` endpoint/AOR (see below).
- `../assets/docker-compose.load_test.override.yml` — load-test-only override
  (the regular suite is unaffected): mounts `pjsip.conf` into the `ari` container
  and adds the `ari-netem` sidecar that injects ARI latency (shares ari's network
  namespace, `cap_add: NET_ADMIN`, installs `iproute2` at start, applies
  `tc qdisc ... netem delay ${ARI_LATENCY_MS}ms`).

## The PICKUPMARK / PJSIP_ENDPOINT requirement

`dial_all_contacts` reads `getChannelVar(PJSIP_ENDPOINT(<aor>,PICKUPMARK))`
*unguarded*. On Asterisk 22 `PICKUPMARK` is **not** a native `PJSIP_ENDPOINT`
field, and with no matching endpoint the read returns HTTP 500 ("Unable to read
provided function"), which kills the StasisStart handler before any
`_PollingContactDialer` is created — so no load is sustained.

The fix is `pjsip.conf` defining a `load-test-aor` endpoint that exposes
`PICKUPMARK` via `set_var` (which `PJSIP_ENDPOINT(...,PICKUPMARK)` reads back) and
an AOR with no contacts (so `PJSIP_DIAL_CONTACTS(load-test-aor)` returns empty and
the dialer polls without originating contact channels). `DIAL_AOR` must equal the
endpoint name. The other read, `PJSIP_DIAL_CONTACTS`, is already error-handled in
`_get_contacts`, so only the `PJSIP_ENDPOINT` read needs the endpoint to exist.
