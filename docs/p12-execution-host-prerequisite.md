# P12 — Linux KVM execution host prerequisite

## Decision and current status

The single preferred production direction remains a dedicated Linux KVM worker pool with
one Firecracker microVM per validation job. P12 did not provision a host, install Firecracker,
create a guest image, or execute repository code. The immediate external prerequisite is an
authorized, dedicated Linux host that exposes usable `/dev/kvm`; this Mac's macOS environment
is not that host. No cloud provider or instance has been selected or purchased.

| Area | P12 status |
| --- | --- |
| Source, snapshot, tenant and evidence identity checks | Implemented; synthetic backend tests passed |
| Structured edits, deterministic diff and static validator | Implemented; synthetic tests passed |
| Fixed synthetic test specifications and comparison outcomes | Implemented; contract tests passed |
| VM request framing and untrusted response parser | Implemented as a non-executing contract; unit tests only |
| Firecracker driver, guest boot and transfer | Not implemented/installed; not tested against a real runner |
| Dedicated Linux KVM host and guest artifacts | Not provisioned |
| Effective guest isolation and escape resistance | Not verified; independent review required |
| Production patch execution | Disabled and unavailable |

`vm_execution.py` constructs a bounded, nonce-bound request for the existing allowlisted
synthetic fixture and can parse bounded response framing. Its own documentation explicitly
states that parsing does not authenticate a VM or prove execution. It has no Firecracker
driver and is not connected as a production executor. `execution_unavailable()` remains the
production fallback. Existing worker lease fencing, cancellation and stale-result checks are
reusable once a real runner has an independently verified trust boundary. The trusted P9
host demonstration remains a separate synthetic record with `sandbox_used=false`.

## Host and artifact requirements

- Provision a dedicated, single-purpose Linux server running Ubuntu Server 24.04 LTS or a
  separately reviewed distribution supported by the pinned Firecracker release.
- Use `x86_64` or `aarch64`, with guest kernel and root filesystem built for the same
  architecture. Validate the selected host kernel against the pinned Firecracker release's
  kernel support policy.
- Require the KVM kernel module and read/write access to `/dev/kvm` for the narrowly scoped
  runner identity. Verify the device and actual VM start; a configuration flag is not proof.
- Provision a pinned stable Firecracker release with its matching `jailer`; verify official
  release signatures/checksums and retain a signed software inventory. Never use debug builds
  or `--no-seccomp`.
- Build or obtain a minimal immutable guest kernel and ext4 root filesystem from a reviewed
  reproducible build. Pin hashes/signatures for both. Include only the fixed test runtime,
  harness and required system files. No package manager or runtime download is available
  inside a job.
- Any cloud host must demonstrate actual `/dev/kvm` availability and the provider's
  virtualization boundary before use. Ordinary virtual instances must not be assumed to
  expose KVM; Firecracker's getting-started documentation identifies bare-metal EC2 as its
  supported KVM path there. This document does not approve cloud provisioning.

The current Firecracker documentation describes Linux x86-64 and AArch64 support, KVM
access, and an Ubuntu 24.04 bare-metal example. Confirm these requirements against the exact
pinned release before procurement: [Firecracker getting started](https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md),
[production host setup](https://github.com/firecracker-microvm/firecracker/blob/main/docs/prod-host-setup.md),
[kernel policy](https://github.com/firecracker-microvm/firecracker/blob/main/docs/kernel-policy.md).

## Job authorization and host boundary

1. The existing API authorizes tenant, repository, investigation, pinned snapshot and
   proposal before issuing a run. A short-lived request must bind proposal/job ID, source
   snapshot and commit, source and patch hashes, fixed test-spec ID/version, resource policy,
   lease token, nonce and expiry. The runner rejects replay, expired grants, unknown tenants,
   unknown specs, stale leases and mismatched hashes before boot.
2. Authenticate the worker-to-runner channel with mutually authenticated service identity
   and scoped job authorization. Rotate certificates/keys. The runner must not accept a
   caller-selected executable or command. The guest receives only approved source bytes,
   patch bytes, a fixed test harness and non-secret request identity. No GitHub token,
   database URL, Redis credential, cloud credential, SSH agent, model key or signing key
   enters the guest.
3. Run Firecracker under `jailer` with its default seccomp filters, separate PID/mount/user
   namespaces, a per-job cgroup and a dedicated unprivileged UID. Enforce CPU, memory, PID
   and I/O limits at the host, not only in guest configuration. Host kernel and microcode
   must be patched under the host's security maintenance policy.
4. Attach **no guest network interface**. Do not create a TAP device or provide NAT, DNS,
   host networking or IPv6. The runner host itself has an egress-denied namespace/firewall
   policy. Do not mount the project, home directory, Docker socket, host service socket,
   device, credential store or writable host path into the guest.
5. Use an immutable read-only guest root and a per-run, quota-limited scratch disk. Stage a
   minimal request-bound input disk or transfer the bounded fixture over one restricted
   vsock protocol. The host chooses every host-side path; the guest cannot submit paths for
   host opening. Limit response bytes, frames, fields and duration.
6. Initial per-job ceilings, subject to measurement and security approval: 2 vCPU, 2 GiB
   RAM, 512 MiB scratch, 64 guest processes, 60 seconds wall time and 1 MiB total captured
   output. Apply cgroup/device limits and a host watchdog. Stop on any unsupported limit or
   unverifiable policy.
7. Bind the host-generated result envelope to the request nonce, lease, fixture/spec,
   snapshot, source/patch hashes, guest image/kernel hashes, Firecracker/jailer versions,
   observed policy, VM identity, exit code, timeout/resource outcomes, bounded diagnostics
   and cleanup status. Authenticate the envelope with a host-held signing key unavailable
   to the guest. This attests what the runner observed; it does not prove test adequacy or
   that a candidate fixes a real bug.
8. Cancellation terminates the owned VMM/cgroup and invalidates the lease. Cleanup removes
   only the run's VM process, virtual devices, scratch disk, sockets and temporary files;
   verify their absence before accepting a terminal result. Retain sanitized audit metadata,
   not source or secrets, according to an approved retention schedule.

## Acceptance before enabling any runner

An independent security review must inspect effective host and guest state and approve the
image build, update process, host hardening, key custody, tenant boundary, data retention and
incident response. Demonstrate:

- Positive: exact synthetic baseline fail / patched pass with the same fixed test spec;
  source, patch, image and request identities verified; results bound to the correct lease;
  no production `TESTS_PASSED` result unless the runner attestation is valid.
- Negative: no guest network/DNS/IPv6, host loopback, host files, credentials, mounts,
  devices or service sockets; read-only root; bounded scratch/output; process, CPU, memory
  and wall-time limits; wrong hash/spec/tenant/lease and replay rejected.
- Failure handling: malformed or oversized input/result, VM boot failure, guest crash,
  timeout, cancellation, resource exhaustion, duplicate delivery, early worker exit, stale
  completion and cleanup failure all fail closed without accepting a passing result.
- Escape and host-containment review, repeated clean/dirty runs, concurrent-run isolation,
  host health checks and forensic logging. Any policy discrepancy blocks activation.

The first acceptance campaign is synthetic-only. After a successful independent review,
separately authorize any real-repository pilot and data handling. No P12 result changes the
disabled production flag or permits host/Docker execution as a fallback.
