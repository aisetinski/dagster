import signal
import sys
import threading
from contextlib import contextmanager

_received_interrupt = {"received": False}


def setup_windows_interrupt_support():
    """ Set SIGBREAK handler to SIGINT on Windows """
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, signal.getsignal(signal.SIGINT))  # pylint: disable=no-member


def _replace_interrupt_signal(new_signal_handler):
    signal.signal(signal.SIGINT, new_signal_handler)
    # Update the windows interrupt signal as well if needed
    setup_windows_interrupt_support()


# Wraps code that we don't want a SIGINT to be able to interrupt. Within this context you can
# use pop_captured_interrupt or check_captured_interrupt to check whether or not an interrupt
# has been received within checkpoitns. You can also use additional context managers (like
# raise_execution_interrupts) to override the interrupt signal handler again.
@contextmanager
def capture_interrupts():
    if threading.current_thread() != threading.main_thread():
        # Can't replace signal handlers when not on the main thread, ignore
        yield
        return

    original_signal_handler = signal.getsignal(signal.SIGINT)

    def _new_signal_handler(_signo, _):
        _received_interrupt["received"] = True

    signal_replaced = False

    try:
        _replace_interrupt_signal(_new_signal_handler)
        signal_replaced = True
        yield
    finally:
        if signal_replaced:
            _replace_interrupt_signal(original_signal_handler)
            _received_interrupt["received"] = False


def check_captured_interrupt():
    return _received_interrupt["received"]


def pop_captured_interrupt():
    ret = _received_interrupt["received"]
    _received_interrupt["received"] = False
    return ret


# During execution, enter this context during a period when interrupts should be raised immediately
# (as a DagsterExecutionInterruptedError instead of a KeyboardInterrupt)
@contextmanager
def raise_interrupts_as(error_cls):
    if threading.current_thread() != threading.main_thread():
        # Can't replace signal handlers when not on the main thread, ignore
        yield
        return

    if _received_interrupt["received"]:
        _received_interrupt["received"] = False
        raise error_cls()

    original_signal_handler = signal.getsignal(signal.SIGINT)

    def _new_signal_handler(signo, _):
        raise error_cls()

    signal_replaced = False

    try:
        _replace_interrupt_signal(_new_signal_handler)
        signal_replaced = True
        yield
    finally:
        if signal_replaced:
            _replace_interrupt_signal(original_signal_handler)
