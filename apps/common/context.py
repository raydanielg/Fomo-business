"""Request-scoped tenant context, stored via contextvars so services/tasks
can resolve the current business without threading it through every call."""

import contextvars

_current_business = contextvars.ContextVar("current_business", default=None)
_current_membership = contextvars.ContextVar("current_membership", default=None)


def set_current_business(business):
    return _current_business.set(business)


def get_current_business():
    return _current_business.get()


def set_current_membership(membership):
    return _current_membership.set(membership)


def get_current_membership():
    return _current_membership.get()


def clear_context():
    _current_business.set(None)
    _current_membership.set(None)
