# tango-vimba-stresstest
Simple script to measure attribute access times for different vimba camera settings.

Beware: The naive polling used is _intentionally bad design_.
For a real application, one should always use the appropriate tango event subscriptions.
However, the goal here is to obtain worst-case access times as a function of vimba camera load...

## Usage

```
> python3 vimbastresstest.py -h
usage: tangovimba_stresstest [-h] fps streamMB subscribe wait totaltime

Measure tango attribute access times with active vimba camera.

positional arguments:
  fps
  streamMB
  subscribe
  wait
  totaltime

optional arguments:
  -h, --help  show this help message and exit
```

To systematically test a range of settings, one may put the parameters in a file and use `xargs`:

```bash
> cat args
1 4 1 1 60
1 8 1 1 60
2 8 1 1 60
1 15 1 1 60
2 15 1 1 60
4 15 1 1 60
1 4 0 1 60
4 15 0 1 60

> cat args | xargs -L1 python3 vimbastresstest.py
```
