# Patch validation and execution boundary

The current static validator parses a deliberately narrow unified-diff format and applies it
**in memory** to verified indexed source. Defaults are at most five files, 300 added/deleted
lines, 100 hunks and 256 KiB of UTF-8 patch text; configuration may lower these limits but
cannot raise them. It rejects missing or mismatched source hashes, mismatched context lines,
duplicate paths, unsafe paths, hidden directories, recognizable credential paths, binary
data, new/deleted/renamed files, unsupported headers and ambiguous newline handling. Only
existing evidence-backed files can change. The current format requires LF-terminated text,
simple portable paths, and `--- a/path` / `+++ b/path` headers; it does not accept the
additional Git `diff --git` header. Snapshot collection admits regular Git blobs only;
the indexed file table does not independently preserve Git file mode.

`workspace_pair` materializes verified bytes in separate temporary baseline and patched
directories with no-follow file creation. The containing directory stays owner-only; the
synthetic files become readable to the non-root container only during the isolated attempt. The
workspace alone is **not** a security sandbox for running source code.

Step P4 adds an opt-in **test-only** adapter for two built-in original synthetic Python
fixtures. `PATCH_SYNTHETIC_EXECUTION_ENABLED` defaults to false and configuration rejects it
outside `APP_ENV=test`. The repository name, synthetic snapshot ID, synthetic commit marker,
entire source bytes and hash, exact patch and hash, trusted test bytes and hash, fixed Python
executable and arguments are checked against [the registry](../apps/api/app/modules/patches/synthetic_specs.py).
No issue, model, user input or repository source may supply commands. A nonmatching input is
blocked before Docker is contacted. These fixture identities are explicitly synthetic; they
are not authenticated Git provenance.

The adapter creates a fresh container per preflight or test, pinned to the previously local
API image ID, with `--pull=never`. It checks ownership labels and the inspected configuration
before starting: network mode `none`, non-root UID/GID, read-only root and fixture mount,
private bounded tmpfs, dropped capabilities, no-new-privileges, no Docker socket mount,
128 MiB memory, eight processes, one CPU and a ten-second wall timeout. Application,
home, root, optional-package and secret directories are masked; the fixed Python command
receives an empty-derived environment. Output is capped and only recognized pass/fail markers
are retained. Each container is inspected before ownership-limited cleanup. These controls
target trusted fixtures on macOS ARM64 with Docker Desktop; they are not a production sandbox
for hostile repositories. Other hosts fail closed.
The probe checks the daemon's effective default seccomp mode, but the current design does
not pin a separately reviewed seccomp profile or independently recheck it inside each test
container. Image provenance, kernel isolation, daemon reconfiguration and hostile-process
escapes require further review before any untrusted-source use.

The adapter never pulls an image and accepts no alternate executable or arbitrary command.
It removes only containers whose exact image, unique name and ownership labels match its own
run, then verifies their absence. If ownership or cleanup cannot be verified, it records a
cleanup failure. A completed comparison requires both independent runs and successful
cleanup. The default worker remains unavailable for nonfixture source even in a test process.
Rollback is to leave the test-only flag false and revert only the P4 code changes after review;
no schema change or normal-service migration was introduced by P4.

Before either fixture test, a separate trusted probe checks the effective UID, seccomp,
capabilities, no-new-privileges, read-only mounts, writable scratch, cgroup memory/process/CPU
limits and network isolation. On 2026-11-13 Docker reported `network=none`, but the original
probe counted **11 sysfs entries, 10 proc/socket interfaces and zero IPv4 routes**. The
adapter stopped before either fixture test.

The P4.1 diagnostic explains the count discrepancy: `bonding_masters` is a sysfs control
file, not an interface. The remaining entries are `lo` and nine virtual tunnel-type devices
visible both in `/proc/self/net/dev` and through the kernel-backed socket interface API.
All nine were down in the diagnostic. Only loopback had a primary IPv4 address or an IPv6
address; the IPv4 route table was empty. IPv6 showed the local loopback route and rejected
default routes. Two simultaneously live diagnostic containers had distinct network-namespace
IDs and the same device names. This establishes neither external connectivity nor its absence;
the reason the kernel creates those devices in each namespace remains unverified. The
diagnostic did not enumerate every possible secondary IPv4 address or probe external endpoints.

The runtime mount table also exposed read-only `/etc/hostname`, `/etc/hosts` and
`/etc/resolv.conf` mounts backed by the Docker VM's filesystem; Docker's declared bind-mount
list did not include them. Their source provenance was not independently established, and no
contents were read. `/proc` and read-only `/sys` additionally expose kernel metadata, including
the `bonding_masters` control file. The observed networking devices belong to the process
network namespace; no claim that they are macOS-host interfaces is made. These metadata and
filesystem exposures have not been accepted as satisfying the sandbox policy.

The strengthened preflight distinguishes sysfs entries from actual sysfs interfaces while
still rejecting any unexpected sysfs entry. It checks IPv6 address and route records,
rejects unknown route formats and flags, requires complete Docker isolation fields and a
`none`-only attachment with no assigned addresses, and checks the actual mount table against
a conservative runtime allowlist. Unknown or unapproved runtime mounts, including the three
observed `/etc` mounts, fail closed. The real final preflight rejected **both** network and
runtime-mount checks; neither fixture ran. No network condition or filesystem restriction was
relaxed. These checks are specific to the reviewed macOS/Docker Desktop test adapter; they do
not establish production-grade isolation or complete IPv4-address and host-metadata coverage.

When a future preflight passes, the same fixed test is intended to run in independent baseline
and patched containers. Reports bind the source, patch, test specification, adapter and
sandbox policy identities to both exit markers and the before/after comparison. A completed
result is accepted only after structural and identity checks; an interrupted or incomplete
run is never marked as passed. Mocked adapter results in unit tests are not evidence of real
execution. No actual baseline-fail/patched-pass or both-pass test has yet run.

Before enabling real repository test execution, a separately reviewed isolation adapter must provide
network denial, no host credentials or Docker socket, restricted filesystem and process
creation, resource limits, timeouts and cleanup. It must accept only operator-approved test
specification IDs, independently verify a complete pinned source workspace, run the same
approved specification in fresh baseline and patched environments, and record exact test
identity and sanitized outputs. A passing patched run is not proof of a fix, especially if
the baseline also passes. The interface and mock outcome comparisons alone do not establish
that any of those controls are implemented.

P5 did not modify the execution adapter or rerun its Docker diagnosis. The P4.1 preflight
remains blocked, the test-only flag remains off by default, and no actual synthetic
before/after comparison has run. A dedicated isolated Linux environment or reviewed sandbox
service could be evaluated in a later, separately authorized milestone; neither is provisioned
or represented as safe by this work.

### P9 — macOS native isolation evaluation

P9 evaluates a separate macOS sandbox for immutable, original synthetic fixtures. In inert
canaries, a macOS sandbox profile denied socket access, process creation with `fork` and
`posix_spawn`, and reading `/private/etc/hosts` with `EPERM`. A literal deny for
`/etc/hosts` alone did not cover its resolved path; any file policy must use canonical paths
and must be verified with canaries. These simple experimental profiles are not evidence
that an adapter's complete policy is enforced. `sandbox-exec` could not be nested in the
managed execution sandbox (exit 71); the canaries required an explicitly permitted tool
execution context. No Docker isolation check was relaxed.

Any native adapter must remain test-only and permit only fixed, verified fixture and test
bytes, not arbitrary repository commands. This macOS policy is not an isolation guarantee
for external code. See the [P9 verification record](verification.md#p9--trusted-synthetic-execution).

The tested strict read allowlist prevented Python startup; the broader working policy does
not prove that all application secrets are inaccessible. P9 therefore leaves native test
execution unavailable. A separate immutable synthetic registry and report validator were
added without worker integration; neither launches fixture code. No before/after test ran.

### P9.1 — VM execution prerequisite

Apple's Virtualization framework is available on the ARM64 Mac, but this inspection found
no verified Linux guest image or dedicated reviewed VM launcher. A support query returned
false inside the managed tool environment; it does not establish host-wide availability.
No VM, guest isolation policy, guest input channel, or fixture execution was verified.
The VM execution contract remains fail closed and does not change the existing Docker
executor. A future implementation must verify effective VM devices, use no network or host
directory shares, bind a bounded input/output channel to the fixture and request, cap CPU,
memory, time and output, and confirm owned guest storage cleanup. Those are requirements,
not established controls. VM execution of real repositories requires a separate review.

### P9 final — trusted synthetic host demonstration

Under a narrow authorization for the exact reviewed arithmetic fixture, four local Python
child processes ran in private disposable workspaces. The original function failed the
approved `assert add(2, 3) == 5` assertion (exit 1), and the disposable copy incorporating
the retained P8 model-generated diff passed that same assertion (exit 0). The existing
comparison logic returned `BASELINE_FAILED_PATCH_PASSED`. A separate control ran the exact
reviewed addition source in two workspaces; both children passed and the comparison was
`BOTH_PASSED`. That control does not demonstrate a repaired regression.

The source, assertion and P8 diff were checked against fixed byte identities before
execution. These child processes ran on the host without an execution sandbox; their
allowlisted content is the safety boundary, and the result records correctly state
`sandbox_used=false`. This demonstration does not establish isolation for untrusted code.
The existing application service does not accept a completed unsandboxed host report as a
publishable execution result, and this host runner is not registered as a production
provider. Real repository execution remains unavailable pending a separately reviewed
isolation boundary. PostgreSQL persistence remains unverified.

## P10 execution architecture decision

**Decision for future real-repository tests:** provision a dedicated Linux worker pool
using one Firecracker microVM per validation job, backed by KVM. This is an architecture
decision only; no runtime, guest image or worker was installed or claimed verified in P10.
RepoPilot currently has a Docker Compose development topology on macOS, but that is not
evidence that Docker Desktop provides the required isolation. Do not route real proposal
jobs to the host, Docker adapter, P9 trusted runner or an unprovisioned VM.

The future pool must use a pinned, reviewed Firecracker binary and `jailer`, a minimal
immutable Linux guest with only the fixed test runtime, and a fresh read-only guest root
plus quota-limited per-job scratch. Proposed initial limits are 2 vCPU, 2 GiB RAM, 512 MiB
scratch, 64 guest processes, 60 seconds wall time and 1 MiB captured output; deployment
owners must validate and approve these values before provisioning. The guest must have no
virtual network device, host directory share, project mount, Docker socket, host service
socket, device passthrough, SSH forwarding or credentials. A bounded request-bound manifest
and fixture bundle may enter through a narrow vsock protocol; only a bounded authenticated
result may return. The Linux host must enforce KVM separation, seccomp, cgroup CPU/memory/PID
limits, an egress-denied jailer namespace, no host secrets in the worker environment,
watchdog termination, and verified cleanup of the VM process and scratch disk.

Before activation, a security review must verify effective configuration (not requested
flags) and pass positive tests for correct baseline/patched outcomes and cleanup, plus
negative tests for guest network access, host-path and secret access, extra devices,
malformed or oversized results, timeout, resource exhaustion, cancellation, duplicate
delivery, stale leases and cleanup failure. The runner remains disabled until the runtime
and image are provisioned, review is approved, PostgreSQL migration/schema checks pass, and
explicit operational enablement is authorized. This is not a production-ready sandbox
claim and does not change the current fail-closed execution requirement.

## P11 PostgreSQL verification update

P11 verified the source-provenance and patch-validation persistence contracts on a private
disposable PostgreSQL 16.16 instance. Alembic reached `0018`; fresh schema drift and the
legacy upgrade path passed. The production execution boundary is unchanged: unsandboxed P9
host evidence remains a separate trusted synthetic demonstration, and no untrusted source
was executed during P11. See [P11 evidence](p11-postgresql-verification.md).

## P12 execution readiness

The complete PostgreSQL backend selection now passes after restoring the already locked
NumPy 2.5.4 wheel to a private test environment; exact results are in the [P12 verification
record](verification.md#p12--numpy-regression-and-backend-completion-2026-11-16). The
production executor remains unavailable. `vm_execution.py` is a non-executing request and
response contract, not a Firecracker driver, and it is not registered with the worker.
`execution_unavailable()` remains fail closed. P9 host results remain `sandbox_used=false`
and cannot satisfy production completion.

The actionable Linux host, guest image, authentication, isolation, resource-limit, cleanup
and independent security acceptance requirements are in the [P12 execution-host
specification](p12-execution-host-prerequisite.md). Until an authorized dedicated Linux KVM
host with a pinned Firecracker/jailer and reviewed guest artifacts is provisioned and passes
that checklist, real-repository tests and production patch execution remain disabled.
