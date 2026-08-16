import os

MINERS = [
    {
        "name": "Ultra1",
        "ip": "192.168.0.175"
    },
    {
        "name": "Ultra2",
        "ip": "192.168.0.172"
    }
]

KS_USER = os.getenv("KS_USER", "admin")
KS_PASSWORD = os.getenv("KS_PASSWORD", "")
