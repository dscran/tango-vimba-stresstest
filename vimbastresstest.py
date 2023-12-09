import time
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import numpy as np
from tango import DeviceProxy, AttributeProxy, EventType, DevState
from typing import List, Dict
import argparse


log = logging.getLogger("stresstest")
log.addHandler(logging.StreamHandler())
log.setLevel(logging.INFO)


FQDN_MICROSCOPE = "haspp04interm:10000/p04/tangovimba/MaxP04_cam"
ATTR_LIST_TEST = [
    "sys/tg_test/1/ampli",
    "sys/tg_test/1/boolean_scalar",
    "sys/tg_test/1/double_scalar",
    "sys/tg_test/1/enum_scalar",
    "sys/tg_test/1/float_image_ro",
    "sys/tg_test/1/State",
    "sys/tg_test/1/long_scalar",
]


ATTR_LIST_MAXP04 = [
    # haspp04interm: vimba cameras
    "haspp04interm:10000/p04/tangovimba/MaxP04_cam/State",
    "haspp04interm:10000/p04/tangovimba/MaxP04_cam/DeviceTemperature",
    # haspp04exp1: steppers, beckhoff, misc
    "haspp04exp1:10000/p04/keithley6517a/exp1_mesh/Current",
    "haspp04exp1:10000/p04/keithley6517a/exp1_mesh/Range",
    "haspp04exp1:10000/p04/keithley6517a/exp1_mesh/State",
    "haspp04exp1:10000/p04/keithley6517a/exp1_mesh/ZeroCheck",
    "haspp04exp1:10000/p04/monop04/exp1.01/EnergyMean",
    "haspp04exp1:10000/p04/monop04/exp1.01/State",
    "haspp04exp1:10000/p04/monop04/exp1.01/Position",
    "haspp04exp1:10000/p04/monop04/exp1.01/Order",
    "haspp04exp1:10000/p04/pyadsadaptor/haspp04beck10_branch1/fast.femto1.target_index",
    "haspp04exp1:10000/p04/pyadsadaptor/haspp04beck10_branch1/fast.femto1_start",
    "haspp04exp1:10000/p04/pyadsadaptor/haspp04beck10_branch1/fast.sample_rate",
    "haspp04exp1:10000/p04/pyadsadaptor/haspp04beck10_branch1/main.cpu_usage",
    "haspp04exp1:10000/p04/pyadsadaptor/haspp04beck10_branch1/main.input7",
    "haspp04exp1:10000/p04/pyadsadaptor/haspp04beck10_branch1/main.input8",
    "haspp04exp1:10000/p04/pyadsadaptor/haspp04beck10_branch1/main.filter_elm_ch1_value",
    "haspp04exp1:10000/p04/pyadsadaptor/haspp04beck10_branch1/fast.femto2.femto_array1",
    "haspp04exp1:10000/p04/pyadsadaptor/haspp04beck10_branch1/fast.femto1.femto_array1",
    "haspp04exp1:10000/p04/motor/exp1_2.01/Position",
    "haspp04exp1:10000/p04/motor/exp1_2.01/State",
    "haspp04exp1:10000/p04/motor/exp1_2.02/Position",
    "haspp04exp1:10000/p04/motor/exp1_2.02/State",
    "haspp04exp1:10000/p04/motor/exp1_2.03/Position",
    "haspp04exp1:10000/p04/motor/exp1_2.03/State",
    "haspp04exp1:10000/p04/motor/exp1_2.04/Position",
    "haspp04exp1:10000/p04/motor/exp1_2.04/State",
    "haspp04exp1:10000/p04/motor/exp1_2.05/Position",
    "haspp04exp1:10000/p04/motor/exp1_2.05/State",
    "haspp04exp1:10000/p04/motor/exp1_2.06/Position",
    "haspp04exp1:10000/p04/motor/exp1_2.06/State",
    # haspp04max: sardana elements, smaract
    "haspp04max:10000/motor/piezojenactrl/0/Position",
    "haspp04max:10000/motor/tm_rmucoordinate_rmu1_hrotz/1/Position",
    "haspp04max:10000/motor/tm_rmucoordinate_rmu1_hrotz/1/State",
    "haspp04max:10000/motor/tm_rmucoordinate_rmu1_vrotx/1/Position",
    "haspp04max:10000/motor/tm_rmucoordinate_rmu1_vrotx/1/State",
    "haspp04max:10000/motor/tm_rmucoordinate_rmu1_hx/1/Position",
    "haspp04max:10000/motor/tm_rmucoordinate_rmu1_hx/1/State",
    "haspp04max:10000/motor/tm_rmucoordinate_rmu1_hz/1/Position",
    "haspp04max:10000/motor/tm_rmucoordinate_rmu1_hz/1/State",
    "haspp04max:10000/motor/tm_rmucoordinate_rmu1_vx/1/Position",
    "haspp04max:10000/motor/tm_rmucoordinate_rmu1_vx/1/State",
    "haspp04max:10000/motor/vm_br1_exitslit/1/Position",
    "haspp04max:10000/motor/vm_br1_exitslit/1/State",
    "haspp04max:10000/motor/vm_br1_master/1/Position",
    "haspp04max:10000/motor/vm_br1_master/1/State",
]


def poll_attribute(fqdn: str, wait: float, totaltime: float) -> List[float]:
    """
    Repeatedly poll attribute and return list of access times.

    Parameters
    ----------
    fqdn
        Fully qualified domain name of tango attribute to poll
    wait
        timeout in seconds between successful polls
    totaltime
        total time in seconds during which to poll attribute

    Returns
    -------
    access_times
        list of access times in milliseconds
    """
    try:
        attr = AttributeProxy(fqdn)
        attr.read()
    except Exception as exc:
        log.error(f"{fqdn}: {exc}")
        return []

    access_times = []

    log.info(f"Start polling {fqdn} for {totaltime} s.")
    time_start = time.time()
    while True:
        t0 = time.time()
        value = attr.read()
        access_times.append(1000 * (time.time() - t0))
        if t0 > (time_start + totaltime):
            break
        time.sleep(wait)
    log.info(f"Finished polling {fqdn}")
    return access_times


def image_handler(event):
    """
    Dummy image event handler

    Parameters
    ----------
    event : tango event
       Event to be handled
    """
    pass


def start_vimbacamera(fqdn: str, fps: float, streamrate: float, subscribe: bool) -> int:
    """
    Start vimba camera with given settings.

    Configures frame rate and data stream rate of vimba camera and registers
    dummy handler for image data.

    Parameters
    ----------
    fqdn
        Fully qualified domain name of tango attribute to poll
    fps
        frames per second
    streamrate
        stream bytes per second
    viewmode
        which image type

    Returns
    -------
    event_id
        Numeric id of event subscription
    """
    event_id = None
    cam = DeviceProxy(fqdn)
    if cam.state() == DevState.MOVING:
        log.warning(f"Camera {fqdn} already running. Stopping it now.")
        cam.StopAcquisition()
    log.info(f"Configuring camera {fqdn}")
    cam.StreamBytesPerSecond = streamrate
    fpsmax = cam.AcquisitionFrameRateLimit
    log.info(f"Max. frame rate: {fpsmax:.2f}")
    cam.AcquisitionFrameRateAbs = min(fps, fpsmax)
    log.info(f"stream rate: {streamrate}, frame rate: {min(fps, fpsmax)}")
    cam.ViewingMode = 1

    if subscribe:
        event_id = cam.subscribe_event("image8", EventType.CHANGE_EVENT, image_handler)
        log.info(f"Subscribing to image8 change event. event_id={event_id}")
    else:
        log.info("Not subscribing to image change event.")

    cam.StartAcquisition()
    log.info(f"Start acquisition.")
    return cam, event_id


def stop_vimbacamera(cam, event_id=None):
    """
    Stop acquisition and unsubscribe events

    Parameters
    ----------
    fqdn
        Fully qualified domain name of tango attribute to poll
    event_id
        Numeric id of event subscription, or None
    """
    if event_id is not None:
        cam.unsubscribe_event(event_id)
        log.info(f"Unsubscribing with event_id={event_id}")
    cam.StopAcquisition()
    log.info("Stop acquisition.")


def worker_attributelist(attributes: List[str], wait: float, totaltime: float) -> Dict:
    """
    Simultaneously start polling several attributes.

    Uses multithreading to poll attributes and returns access times.

    Parameters
    ----------
    attributes
        list of tango attribute names to poll
    wait
        timeout between polls
    totaltime
        total time in seconds during which to poll attribute

    Returns
    -------
    timings
        dictionary of {"attribute": [access_times], ...}
    """
    func_poll = partial(poll_attribute, wait=wait, totaltime=totaltime)
    with ThreadPoolExecutor(len(attributes)) as executor:
        timings = executor.map(func_poll, attributes)
    return {attr: times for attr, times in zip(attributes, timings)}


def save_timings(fname: str, timings: Dict):
    """
    Save access timings as csv file.

    Parameters
    ----------
    fname
        filename or file object with write method
    timings
        timing result dictionary from worker_attributelist
    """
    maxrows = max([len(v) for v in timings.values()])
    data = np.nan * np.ones((len(timings), maxrows))
    for i, v in enumerate(timings.values()):
        data[i, :len(v)] = v
    header = ", ".join(timings.keys())
    np.savetxt(fname, data.T, fmt="%.3f", delimiter=",", header=header)


def main(fps=2, streamMB=1.5, subscribe=True, wait=1, totaltime=30):
    cam, event_id = start_vimbacamera(FQDN_MICROSCOPE, fps, int(1e6 * streamMB), True)
    results = worker_attributelist(ATTR_LIST_MAXP04, wait, totaltime)
    stop_vimbacamera(cam, event_id)
    tstamp = time.strftime("%Y%m%d_%H%M%S")
    csvname = f"timings_{tstamp}.csv"
    info = [
        f"fps={fps}",
        f"streamMB={streamMB}",
        f"subscribe={subscribe}",
        f"wait={wait}",
        f"totaltime={totaltime}"
    ]
    info_header = "\n".join(["# " + v for v in info]) + "\n"
    with open(csvname, "w") as f:
        f.write(info_header)
        save_timings(f, results)
    log.info(f"Results saved to {csvname}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='tangovimba_stresstest',
        description='Measure tango attribute access times with active vimba camera.',
    )
    parser.add_argument("fps", type=float, default=2)
    parser.add_argument("streamMB", type=float, default=6)
    parser.add_argument("subscribe", type=bool, default=True)
    parser.add_argument("wait", type=float, default=1)
    parser.add_argument("totaltime", type=float, default=30)
    args = parser.parse_args()
    main(**vars(args))
