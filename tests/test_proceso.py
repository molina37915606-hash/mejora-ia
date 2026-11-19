"""Prueba de punta a punta, sin motor IA, del envío a disco y exportación."""
import io
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.request import Request, urlopen

from PIL import Image
import server


class ProcessingTests(unittest.TestCase):
    def test_envio_procesamiento_y_descarga(self):
        listener = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=listener.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(listener.server_port)
        sample = io.BytesIO()
        Image.new("RGB", (24, 16), (30, 100, 180)).save(sample, format="PNG")
        try:
            with patch.object(server, "record", return_value=None):
                request = Request(base + "/process", sample.getvalue(), method="POST", headers={
                    "X-Scale": "2", "X-Mode": "fiel",
                    "X-Performance": "low", "X-Filename": "prueba.png"
                })
                with urlopen(request, timeout=15) as response:
                    job = json.load(response)["job"]
                result = None
                for _ in range(100):
                    with urlopen(base + "/job/" + job, timeout=5) as response:
                        result = json.load(response)
                    if result["state"] != "running":
                        break
                    time.sleep(0.1)
                self.assertEqual(result["state"], "done", result.get("error"))
                with urlopen(base + "/export/" + job, timeout=15) as response:
                    payload = response.read()
                with Image.open(io.BytesIO(payload)) as output:
                    self.assertEqual(output.size, (48, 32))
                    self.assertEqual(output.getpixel((8, 8)), (30, 100, 180))
                with urlopen(Request(base + "/discard/" + job, b"", method="POST"), timeout=5):
                    pass
        finally:
            listener.shutdown()
            listener.server_close()


if __name__ == "__main__":
    unittest.main()
