# Device selection safety: unresolved

The GUI retains the index returned by `list --json`; RGB and effect commands
pass that index to a new bridge invocation, which enumerates again. If order
changes, the command may open a different device. The strict-xfail regression
in `tests/test_selection_regression.py` exercises the GUI's RGB argument
builder and actual bridge list/command handlers against a fake HID backend.
Remove its xfail when the bug is fixed. It is not a physical hardware test.

## Why a simple identity selector is insufficient

`physical_id()` can fall back to an empty or duplicated serial; grouping then
merges devices with the same vendor, product and identity. A sysfs USB port,
hidraw path or serial may be reused, missing or duplicated. Even a unique
serial and path observed at two instants cannot prove that a device with the
same descriptors was not unplugged and replaced between them. Enumeration
followed by open also has a race: the path may change ownership after the
check. Thus a mock that only compares snapshots cannot validate the requested
replacement guarantee. No production selection change is made here.

## Candidate design and acceptance criteria

Use a long-lived bridge owning device handles and monitoring kernel device
lifecycle, instead of re-enumerating by GUI index for each command. Bind GUI
selection to an opaque session-scoped token representing a particular live
attachment, not just descriptors; invalidate it on remove, monitor overflow,
bridge restart, incomplete monitoring, or uncertainty. Establish monitoring
before enumeration and reconcile events around opening; inspect the opened
handle's kernel identity and fail closed if it cannot be verified against the
attachment. Never fall back to opening by VID/PID for token-based requests.
A device that cannot be uniquely bound must be unavailable with a clear error.
This is a proposal, not a demonstrated race-free implementation; platform
APIs and event/handle guarantees must be researched and verified first.

Add tests with controllable fake enumeration, lifecycle events and opens for:
reorder targeting the same attachment; removal before command and during open;
duplicate/missing identity and interfaces; replacement at the same path with
identical descriptors, including remove/add between scan and open; monitor
failure/overflow and bridge restart; and every GUI command including effects.
Assert no writes to another attachment even if an error is returned. Test
multi-interface grouping and both live and bounded effects. Document the
remaining kernel/backend assumptions and exercise actual hardware separately.
Do not silently change the existing explicit CLI index semantics without a
compatibility decision.
