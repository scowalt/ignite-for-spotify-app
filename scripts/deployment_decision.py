def decide_deployment(active, candidate, failed_digests, interrupted):
    if interrupted is not None:
        phase = interrupted.get('phase')
        if phase in ['verified', 'committed'] and interrupted.get('candidate_digest') == active['artifact_digest']:
            return 'finalize_commit'
        if phase == 'rolled_back':
            return 'finalize_rollback'
        if phase in ['accepted', 'preflighted', 'backup_started', 'backup_verified', 'switch_started', 'backend_healthy', 'dependents_changed', 'verified']:
            return 'recover_prior'
        return 'manual_recovery'
    if candidate is None:
        return 'waiting'
    if active['artifact_digest'] == candidate['artifact_digest']:
        return 'unchanged'
    if candidate['artifact_digest'] in failed_digests:
        return 'failed_release_fenced'
    if tuple(candidate['order']) <= tuple(active['order']):
        return 'stale_release'
    return 'deploy'
