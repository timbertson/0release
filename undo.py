import sys
import os

import release
import support
from scm import get_scm
from zeroinstall import SafeException

# A module to help the user revert as many non-idempotent
# changes as possible that happened during a release (which presumably
# failed at some point), so that it may be attempted again without
# manually having to undo the work (which is error prone).

def banner(text):
	print '-' * 50
	print text

def undo(local_iface, options):
	assert options.master_feed_file
	status = support.Status()
	scm = get_scm(local_iface, options)

	steps = []
	def step(fn):
		steps.append(fn)
		return fn

	@step
	def undo_master_feed():
		'''Revert to a backup of the master feed'''
		if status.updated_master_feed:
			banner("Reverting master feed file (%s):" % (options.master_feed_file,))
			if not os.path.exists(options.master_feed_file):
				print "NOTE: Master feed file doesn't exist - skipping this step."
				status.updated_master_feed = False
				return
			if support.revert_backup(options.master_feed_file):
				status.updated_master_feed = False
			else:
				print("Perhaps this is the first release? If so, you can safely delete %s" % (options.master_feed_file,))
				return 1

	@step
	def undo_tag():
		'''Delete SCM tag'''
		if status.tagged:
			banner("Un-tagging released version")
			scm.remove_tag(status.release_version)
			status.tagged = False

	@step
	def undo_commits():
		'''Reset to original HEAD'''
		if status.head_before_release:
			scm.ensure_committed()
			banner("Reverting to commit: %s" % (status.head_before_release,))
			scm.reset_hard(status.head_before_release)
			status.head_before_release = None

	@step
	def undo_other_metadata():
		'''Revert other metadata'''
		banner("Reverting metadata")
		status.src_tests_passed = None
		status.verified_uploads = None
		status.created_archive = False
		status.new_snapshot_version = None
		status.release_version = None
		status.head_at_release = None
		status.old_snapshot_version = None

	errors = 0
	for step in steps:
		try:
			step_errors = step()
			if step_errors:
				errors += step_errors
		except (StandardError, SafeException):
			banner("Step FAILED: %s" % (step.__doc__,))
			import traceback
			traceback.print_exc(file=sys.stdout)
			errors += 1
			banner("")

	status.save()

	if errors == 0:
		nonzero_keys = [k for k,v in status.to_dict().items() if v]
		assert len(nonzero_keys) == 0, "Oops! I don't know how to revert: %s" % (", ".join(sorted(nonzero_keys)),)
		print "Successfully reverted, you should be ready to try again now."
		return 0
	print ''
	banner("%s errors encountered" % (errors,))
	return errors
