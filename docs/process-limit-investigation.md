# Process/thread limit incident

Observed old Codex container: pids.current251, pids.max256, pids.events max211;
memory about755MiB of1536MiB and no recorded cgroup OOM. Host docker top showed
8 adapter chains and251 total threads, without zombie processes in that sample.
This proves limit pressure; it does not prove a leak or the absence of a leak.
The pinned Buzz runtime eagerly builds the requested pool, and each Codex adapter
starts multiple processes and threads. Approval review can need more capacity.

New policy: max(256,128+64*workers), so10 workers gets768 and32 gets2176.
This is finite initial headroom, not a workload guarantee. CPU/RAM limits remain;
raising a PID ceiling does not reserve CPU/RAM or make10 workers fit every VPS.
Parallelism remains user-controlled1..32, default10. Guardian remains enabled.
Old registry entries retain256 until explicitly redeployed. A running container
with mismatched limits is rejected before mutation. Stop the bot in setup and
redeploy from Buzz; provider login, workspace, identity and quota are retained.
A management-project restart alone does not recreate existing bot containers.

Native supervisors collect bounded cgroup-v2 snapshots every5seconds without
spawning docker exec. Portal shows last sampled usage and categorized warnings.
The lifetime event counter is separate from the per-launch baseline/delta;
a historical counter by itself is not reported as a new failure. Samples may
be unavailable on systems that do not expose the expected cgroup-v2 files.
Snapshots are latest state, not a historical time-series database.

Before release acceptance, record host-side docker top PID/PPID/NLWP/STAT/COMM
(no command arguments or environment) and these snapshots at: warm idle, after
repeated successful tasks, after failures, after stop, and after a new launch.
Compare idle thread counts after the pool has settled, not startup versus a full
pool. A sustained rising idle baseline or surviving old process trees warrants
further investigation. Check both Claude and Codex, including approval review.
Never infer leak-free behavior from a single snapshot or merely raise limits
repeatedly. Finally turn Windows fully off and run a new scheduled VPS task.
These live checks have not been completed by this local patch.
