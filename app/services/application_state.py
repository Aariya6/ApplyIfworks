from ..db import get_application, update_application, log_event
# Every pre-submission state can also end in SUBMITTED_MANUAL: the person applied themselves
# through the official link and told the tracker so. It carries no automated confirmation
# evidence — that's the honest distinction from SUBMITTED_CONFIRMED.
_MANUAL={'SUBMITTED_MANUAL'}
# Outcome states, added on top of the existing (unchanged, working) pre-submission funnel.
# These are never inferred automatically -- there is no email/ATS-status integration -- they are
# only ever set by the person telling the tracker what actually happened (see
# main.py's /job/{id}/outcome route). WITHDRAWN and REJECTED are reachable from any live outcome
# state, since either can happen at any stage.
_OUTCOME={'RECRUITER_RESPONSE','ASSESSMENT','INTERVIEW','FINAL','OFFER','REJECTED','WITHDRAWN'}
_OUTCOME_FLOW={
 'RECRUITER_RESPONSE':{'ASSESSMENT','INTERVIEW','FINAL','OFFER','REJECTED','WITHDRAWN'},
 'ASSESSMENT':{'INTERVIEW','FINAL','OFFER','REJECTED','WITHDRAWN'},
 'INTERVIEW':{'FINAL','OFFER','REJECTED','WITHDRAWN'},
 'FINAL':{'OFFER','REJECTED','WITHDRAWN'},
 'OFFER':{'REJECTED','WITHDRAWN'},  # an offer can still be declined (WITHDRAWN) or fall through
 'REJECTED':set(), 'WITHDRAWN':set(),
}
ALLOWED={
 # REQUIRES_REVIEW is reachable from every pre-READY state too: apply_job() can bail out this
 # early (no apply_url yet, no tailored resume yet, no letter yet) before it ever reaches READY,
 # e.g. when Dry Run is clicked before Tailor CV.
 'DISCOVERED':{'SHORTLISTED','TAILORING','READY','FAILED_DISCOVERY','REQUIRES_REVIEW'}|_MANUAL,
 'SHORTLISTED':{'TAILORING','READY','FAILED_DISCOVERY','REQUIRES_REVIEW'}|_MANUAL,
 'TAILORING':{'READY','FAILED_TAILORING','REQUIRES_REVIEW'}|_MANUAL,
 'TAILORED':{'READY','LETTER_READY','FAILED_TAILORING','REQUIRES_REVIEW'}|_MANUAL,
 'LETTER_READY':{'READY','FAILED_TAILORING','REQUIRES_REVIEW'}|_MANUAL,
 'READY':{'DRY_RUN','BROWSER_OPENED','FAILED_FORM'}|_MANUAL,
 'DRY_RUN':{'READY','FAILED_FORM'}|_MANUAL,
 'BROWSER_OPENED':{'FORM_ANALYZED','REQUIRES_HUMAN','FAILED_FORM'},
 'FORM_ANALYZED':{'FORM_FILLED','REQUIRES_HUMAN','FAILED_FORM'},
 'FORM_FILLED':{'DRY_RUN','READY_TO_SUBMIT','REQUIRES_HUMAN','REQUIRES_REVIEW'},
 'READY_TO_SUBMIT':{'SUBMITTING','REQUIRES_REVIEW'}, 'SUBMITTING':{'SUBMITTED_CONFIRMED','SUBMIT_CLICKED_REVIEW','FAILED_FORM'},
 # Outcome states now reachable from every real "applied" state, in addition to staying terminal
 # (a submitted application with no recorded outcome yet is still valid -- that's the common case).
 'SUBMITTED_CONFIRMED':set(_OUTCOME), 'SUBMITTED_MANUAL':set(_OUTCOME),
 'REQUIRES_HUMAN':{'READY','FAILED_FORM'}|_MANUAL,
 'REQUIRES_REVIEW':{'READY','FAILED_FORM'}|_MANUAL,
 'SUBMIT_CLICKED_REVIEW':{'READY','REQUIRES_REVIEW','SUBMITTED_CONFIRMED'}|_MANUAL|_OUTCOME,
 'FAILED_DISCOVERY':set(),'FAILED_TAILORING':set(),'FAILED_FORM':{'READY','BROWSER_OPENED','REQUIRES_REVIEW'}|_MANUAL,
}
for _state,_targets in _OUTCOME_FLOW.items():
    ALLOWED[_state]=_targets
def transition(aid,new,detail=''):
    current=(get_application(aid) or {}).get('status')
    if current==new:return True
    if current not in ALLOWED or new not in ALLOWED[current]: raise ValueError(f'Invalid application transition: {current} -> {new}')
    update_application(aid,status=new); log_event(aid,'STATE_TRANSITION',f'{current} -> {new}: {detail}'); return True
