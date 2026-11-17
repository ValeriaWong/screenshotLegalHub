from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class RecordMixin:
    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(String, index=True, default='')
    run_id: Mapped[str] = mapped_column(String, index=True, default='')
    body: Mapped[dict] = mapped_column(JSON)

TABLES = ['cases', 'parties', 'evidence_items', 'messages', 'events', 'source_refs', 'matter_selections',
          'analysis_runs', 'skill_runs', 'case_claims', 'case_elements', 'fact_propositions', 'burden_assignments',
          'evidence_links', 'evidence_gaps', 'contradictions', 'strategy_items', 'review_decisions',
          'analysis_snapshots', 'case_plans', 'run_events', 'review_gates', 'egress_audit', 'reconciliations', 'lawyer_assessments',
          'local_users', 'model_configs', 'user_settings', 'auth_users', 'auth_sessions', 'active_perceptions']
MODELS = {name: type(name.title().replace('_', ''), (RecordMixin, Base), {'__tablename__': name}) for name in TABLES}
