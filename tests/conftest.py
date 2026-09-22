"""Fixtures compartidos: impresora de red simulada (sink TCP)."""
import socket
import threading

import pytest


class FakePrinter:
    """
    Servidor TCP en 127.0.0.1 que hace de impresora de red: acepta conexiones,
    lee todos los bytes y los guarda. Uso como context manager o fixture.
    """

    def __init__(self) -> None:
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))  # puerto efimero
        self._srv.listen(16)
        self.host, self.port = self._srv.getsockname()
        self.jobs: list[bytes] = []
        self._lock = threading.Lock()
        self._stop = False
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        while not self._stop:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        chunks = bytearray()
        conn.settimeout(5.0)
        try:
            while True:
                buf = conn.recv(65536)
                if not buf:
                    break
                chunks += buf
        except OSError:
            pass
        finally:
            conn.close()
        with self._lock:
            self.jobs.append(bytes(chunks))

    def wait_for_jobs(self, n: int, timeout: float = 5.0) -> bool:
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if len(self.jobs) >= n:
                    return True
            time.sleep(0.02)
        return False

    def close(self) -> None:
        self._stop = True
        try:
            self._srv.close()
        except OSError:
            pass

    def __enter__(self) -> "FakePrinter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


@pytest.fixture
def fake_printer():
    fp = FakePrinter()
    try:
        yield fp
    finally:
        fp.close()
