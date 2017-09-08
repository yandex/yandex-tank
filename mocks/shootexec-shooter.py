#!/usr/bin/env python

import sys
import time
import random

stdout = open(sys.argv[1], "w")
stderr = open(sys.argv[2], "w")

waitfor = time.time() + 60 * 2
fake_rps = 1
while time.time() < waitfor:
    # shooting results
    output = [
        time.time(),
        random.choice(["tag1", "tag2", "tag3"]),
        int(500 * random.random()),
        10,
        10,
        int(400 * random.random()),
        10,
        0,
        int(1024 * random.random()),
        int(1024 * random.random()),
        0,
        random.choice([200, 404, 503])
    ]
    stdout.write("\t".join([str(x) for x in output]) + "\n")
    stdout.flush()

    # shooter stats
    stats = [
        time.time(),
        fake_rps,
        1
    ]
    stderr.write("\t".join([str(x) for x in stats]) + "\n")
    stderr.flush()

    fake_rps += 100
    time.sleep(0.3)

sys.exit(0)
