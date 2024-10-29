import logging
from datetime import timedelta

import pytest
from django.utils import timezone

from sentry.taskworker.registry import TaskNamespace
from sentry.taskworker.retry import Retry, RetryError
from sentry.taskworker.task import Task
from sentry.testutils.helpers.task_runner import TaskRunner


def do_things() -> None:
    logging.info("Ran do_things")


@pytest.fixture
def task_namespace() -> TaskNamespace:
    return TaskNamespace(
        name="tests", topic="task-worker", deadletter_topic="task-worker-dlq", retry=None
    )


def test_define_task_defaults(task_namespace: TaskNamespace) -> None:
    task = Task(name="test.do_things", func=do_things, namespace=task_namespace, retry=None)
    assert task.deadline_timestamp is None
    assert task.retry is None
    assert not task.idempotent
    assert task.name == "test.do_things"


def test_define_task_retry_and_deadline(task_namespace: TaskNamespace) -> None:
    retry = Retry(times=3, deadletter=True)
    task = Task(
        name="test.do_things", func=do_things, namespace=task_namespace, retry=retry, deadline=600
    )
    assert task.retry == retry
    assert task.deadline_timestamp is not None
    assert task.deadline_timestamp <= int((timezone.now() + timedelta(seconds=600)).timestamp())

    task = Task(
        name="test.do_things_delta",
        func=do_things,
        namespace=task_namespace,
        retry=retry,
        deadline=timedelta(minutes=10),
    )
    assert task.deadline_timestamp is not None
    assert task.deadline_timestamp <= int((timezone.now() + timedelta(minutes=10)).timestamp())


def test_delay_taskrunner_immediate_mode(task_namespace: TaskNamespace) -> None:
    calls = []

    def test_func(*args, **kwargs) -> None:
        calls.append({"args": args, "kwargs": kwargs})

    task = Task(
        name="test.test_func",
        func=test_func,
        namespace=task_namespace,
        retry=None,
    )
    # Within a TaskRunner context tasks should run immediately.
    # This emulates the behavior we have with celery.
    with TaskRunner():
        task.delay("arg", org_id=1)
        task.apply_async("arg2", org_id=2)

    assert len(calls) == 2
    assert calls[0] == {"args": ("arg",), "kwargs": {"org_id": 1}}
    assert calls[1] == {"args": ("arg2",), "kwargs": {"org_id": 2}}


def test_should_retry(task_namespace: TaskNamespace) -> None:
    retry = Retry(times=3, deadletter=True)
    state = retry.initial_state()

    task = Task(
        name="test.do_things",
        func=do_things,
        namespace=task_namespace,
        retry=retry,
    )
    err = RetryError("try again plz")
    assert task.should_retry(state, err)

    state.attempts = 3
    assert not task.should_retry(state, err)

    no_retry = Task(
        name="test.no_retry",
        func=do_things,
        namespace=task_namespace,
        retry=None,
    )
    assert not no_retry.should_retry(state, err)


def test_create_activation(task_namespace: TaskNamespace) -> None:
    no_retry_task = Task(
        name="test.no_retry",
        func=do_things,
        namespace=task_namespace,
        retry=None,
    )

    retry = Retry(times=3, deadletter=True)
    retry_task = Task(
        name="test.with_retry",
        func=do_things,
        namespace=task_namespace,
        retry=retry,
    )

    # No retries will be made as there is no retry policy on the task or namespace.
    activation = no_retry_task.create_activation("arg", "arg2", org_id=1)
    assert activation.taskname == "test.no_retry"
    assert activation.namespace == task_namespace.name
    assert activation.retry_state
    assert activation.retry_state.attempts == 0
    assert activation.retry_state.discard_after_attempt == 1

    activation = retry_task.create_activation("arg", "arg2", org_id=1)
    assert activation.taskname == "test.with_retry"
    assert activation.namespace == task_namespace.name
    assert activation.retry_state
    assert activation.retry_state.attempts == 0
    assert activation.retry_state.discard_after_attempt == 0
    assert activation.retry_state.deadletter_after_attempt == 3
