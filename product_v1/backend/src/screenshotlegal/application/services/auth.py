import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from sqlalchemy import select
from screenshotlegal.domain.common.models import now
from screenshotlegal.domain.settings.auth import UserView
from screenshotlegal.infrastructure.db.models import MODELS

COOKIE = 'screenshotlegal_session'


class AuthError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def password_hash(password):
    if not 12 <= len(password) <= 128:
        raise ValueError('Password must contain 12 to 128 characters')
    salt = secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return salt.hex()+':'+value.hex()


def password_matches(password, encoded):
    if len(password)>128:
        return False
    salt, expected = encoded.split(':')
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32)
    return hmac.compare_digest(value.hex(), expected)


class AuthService:
    def __init__(self, repo, settings):
        self.repo, self.settings = repo, settings
        self.lock = Lock()
        self.attempts = defaultdict(deque)
        self.dummy_hash = password_hash(secrets.token_urlsafe(24))

    def view(self, row):
        return UserView.model_validate({k: row[k] for k in UserView.model_fields if k in row})

    def initialized(self):
        return bool(self.repo.list('auth_users'))

    def create_user(self, request, bootstrap=False):
        username = request.username.strip().lower()
        encoded = password_hash(request.password.get_secret_value())
        if not request.display_name.strip():
            raise ValueError('Display name is required')
        # BEGIN IMMEDIATE serializes initial-admin creation across server processes.
        with self.repo.session.begin() as session:
            session.connection().exec_driver_sql('BEGIN IMMEDIATE')
            users = list(session.scalars(select(MODELS['auth_users'])))
            if bootstrap and users:
                raise AuthError(403, 'Initial administrator already exists')
            if any(user.id == username for user in users):
                raise ValueError('Username already exists')
            row = dict(id=username, username=username, display_name=request.display_name.strip(), organization='',
                       password_hash=encoded, role='admin' if bootstrap else request.role, enabled=True, created_at=now())
            session.add(MODELS['auth_users'](id=username, case_id='', run_id='', body=row))
            if bootstrap:
                for case in session.scalars(select(MODELS['cases'])):
                    if not case.body.get('owner_id'):
                        case.body = dict(case.body, owner_id=username, members={})
        return self.view(row)

    def login(self, request, remote):
        username = request.username.lower()
        bucket_key = (remote, username)
        with self.lock:
            bucket = self.attempts[bucket_key]
            while bucket and bucket[0] < time.monotonic()-900:
                bucket.popleft()
            if len(bucket)>=5:
                raise AuthError(429, 'Too many login attempts; try again later')
            bucket.append(time.monotonic())
        row = self.repo.optional('auth_users', username)
        valid = password_matches(request.password.get_secret_value(), row['password_hash'] if row else self.dummy_hash)
        if not row or not row['enabled'] or not valid:
            raise AuthError(401, 'Invalid username or password')
        with self.lock:
            self.attempts.pop(bucket_key, None)
        token = secrets.token_urlsafe(32)
        id = hashlib.sha256(token.encode()).hexdigest()
        self.repo.put('auth_sessions', id, dict(user_id=username, expires_at=(datetime.now(timezone.utc)+timedelta(hours=self.settings.session_hours)).isoformat()), immutable=True)
        return self.view(row), token

    def current(self, token):
        if not token:
            raise AuthError(401, 'Login required')
        session = self.repo.optional('auth_sessions', hashlib.sha256(token.encode()).hexdigest())
        if not session or datetime.fromisoformat(session['expires_at']) <= datetime.now(timezone.utc):
            raise AuthError(401, 'Session expired; log in again')
        row = self.repo.optional('auth_users', session['user_id'])
        if not row or not row['enabled']:
            raise AuthError(401, 'Account unavailable')
        return self.view(row)

    def logout(self, token):
        id = hashlib.sha256(token.encode()).hexdigest()
        if self.repo.optional('auth_sessions', id):
            self.repo.delete('auth_sessions', id)

    def admin(self, user):
        if user.role!='admin':
            raise AuthError(403, 'Administrator permission required')

    def users(self):
        return [self.view(u) for u in self.repo.list('auth_users')]

    def revoke_sessions(self, id):
        with self.repo.session.begin() as transaction:
            for row in transaction.scalars(select(MODELS['auth_sessions'])):
                if row.body['user_id']==id:
                    transaction.delete(row)

    def update_user(self, id, request):
        with self.repo.session.begin() as session:
            session.connection().exec_driver_sql('BEGIN IMMEDIATE')
            row = session.get(MODELS['auth_users'], id)
            if row is None:
                raise KeyError('User not found')
            active_admins = [u for u in session.scalars(select(MODELS['auth_users'])) if u.body['role']=='admin' and u.body['enabled']]
            if row.body['role']=='admin' and row.body['enabled'] and len(active_admins)==1 and (request.role!='admin' or not request.enabled):
                raise ValueError('Cannot disable or demote the last administrator')
            row.body = dict(row.body, **request.model_dump())
            result = self.view(row.body)
        self.revoke_sessions(id)
        return result

    def change_password(self, user, request):
        encoded=password_hash(request.new_password.get_secret_value())
        with self.repo.session.begin() as session:
            session.connection().exec_driver_sql('BEGIN IMMEDIATE')
            row=session.get(MODELS['auth_users'],user.id)
            if not password_matches(request.current_password.get_secret_value(),row.body['password_hash']):
                raise AuthError(403,'Current password is incorrect')
            row.body=dict(row.body,password_hash=encoded)
        self.revoke_sessions(user.id)

    def case_role(self, user, case):
        if user.role=='admin' or case.get('owner_id')==user.id:
            return 'owner'
        return case.get('members', {}).get(user.id)

    def access(self, user, id, write=False, owner=False):
        case = self.repo.get('cases', id)
        role = self.case_role(user, case)
        if role is None:
            raise AuthError(404, 'Resource not found')
        if (owner and role!='owner') or (write and role not in ['owner','editor']):
            raise AuthError(403, 'Insufficient case permission')
        return dict(case, access_role=role)

    def share(self, user, case_id, request):
        with self.repo.session.begin() as session:
            session.connection().exec_driver_sql('BEGIN IMMEDIATE')
            record=session.get(MODELS['cases'],case_id)
            if record is None:
                raise KeyError('Case not found')
            case=record.body
            if self.case_role(user,case)!='owner':
                raise AuthError(403,'Owner permission required')
            target=session.get(MODELS['auth_users'],request.username.lower())
            if target is None:
                raise KeyError('User not found')
            if target.id==case.get('owner_id'):
                raise ValueError('Owner permission cannot be changed through sharing')
            members=dict(case.get('members',{}))
            if request.role=='remove':
                members.pop(target.id,None)
            else:
                if not target.body['enabled']:
                    raise ValueError('Cannot share with a disabled account')
                members[target.id]=request.role
            record.body=dict(case,members=members)
        return self.members(user,case_id)

    def members(self, user, case_id):
        case = self.access(user, case_id)
        return [dict(username=id, role=role) for id, role in case.get('members', {}).items()]
