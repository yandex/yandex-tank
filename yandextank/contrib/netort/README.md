# The Netort library

This is a library of common components for performance testing tools (YandexTank, Volta, etc.).

## Data Manager

Data Manager collects your data and stores them to the backends of your choice.

### Key concepts

Core concept is a *test*. Test is a collection of data streams described with metadata (i.e. test name, author, tool, etc.). Each data
stream is also described with its own metadata (i.e., type: monitoring, host: my-backend-server, resource: cpu, etc.).

Data stream is a sequence of values indexed with a timestamp in microseconds. There are two types of data streams currently supported:
    * metrics — a stream of floating point numbers
    * events — a stream of strings

Metrics are used to describe a variable that changes in time (voltage measurements of a phone battery, cpu load, response time, etc.).
Events are used to describe a sequence of events (server response codes, log messages).

Both metrics and events could be aggregated by seconds. Different sets of statistics are calculated for them:
    * quantiles, average, standard deviation and distribution for metrics
    * histogram for events

Test is created during a *Data Session*. One data session — one test.

### Typical workflow

1. Specify the backends you want to save your data to
2. Create a data session, describing it with metadata
3. Subscribe the backends to the data session
4. Create metrics and events in the data session, describing them with metadata
5. Add data to the metrics and events (this might be done in realtime chunk by chunk)
6. Close the data session

```
import numpy as np
import pandas as pd
from netort.data_manager import data_session
from netort.data_manager.clients import LunaClient, LocalStorageClient

# Prepare data

# random metrics
voltage_df = pd.DataFrame()
voltage_df["ts"] = (np.arange(0,1000000,100)
voltage_df["value"] = np.random.randint(1000000, size=10000))

current_df = pd.DataFrame()
current_df["ts"] = (np.arange(0,1000000,100)
current_df["value"] = np.random.randint(1000000, size=10000))

# events
logs_df = pd.DataFrame([
        [0, "log message 1"],
        [11345, "my event number 1"],
        [100345, "my event number 2"],
        [102234, "my event number 3"],
        [103536, "my event number 4"],
    ],
    columns=["ts", "value"])

errors_df = pd.DataFrame([
        [110, "error 1"],
        [11845, "error 2"],
        [13845, "error 3"],
        [202234, "error 4"],
        [203536, "error 5"],
    ],
    columns=["ts", "value"])

# specify backends (1)
luna = LunaClient(  # store to Luna service
    store_raw=False,  # if data stream has aggregates, upload only aggregates without raw data
    api_address="http://example.org")
local = LocalStorageClient()  # store to local files

# create the data session (2)
# It will close automatically (6) because we've used a context manager
with data_session(dict(name="My first test")) as ds:
    ds.subscribe(luna, local)  # subscribe the backends (3)

    # create metrics and events (4)
    voltage = ds.new_metric(dict(name="Voltage"))
    current = ds.new_metric(dict(name="Current"), aggregate=True)  # this metric will be aggregated
    logs = ds.new_events(dict(name="Log messages"))
    error_codes = ds.new_events(dict(name="Error codes), aggregate=True)  # these events will be aggregated

    # add data (5)
    voltage.put(voltage_df)
    current.put(current_df)
    logs.put(log_df)
    error_codes.put(errors_df)
```

## Resource Manager

TODO: describe this

## Data Processing components

TODO: describe this

## Logging components

TODO: describe this

## Config Validator

TODO: describe this
