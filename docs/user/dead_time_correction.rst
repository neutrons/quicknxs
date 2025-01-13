.. _dead_time_correction:

SingleReadoutDeadTimeCorrection
===============================

Dead time is the time after an event that a detector is not able to detect another event.
For a paralyzable detector, an event that happens during the dead time restarts the dead time. For
a non-paralyzable detector, the event is simply lost and does not cause additional dead time.

Dead-time correction corrects for detector dead time by weighing the events according to:

.. math:: N = M \frac{1}{(1-\mathrm{rate} \cdot (\frac{t_{\mathrm{dead}}}{t_{\mathrm{bin}}}))}

for non-paralyzable detectors and

.. math:: N = M \frac{\mathrm{Re} (\mathrm{W}(-\mathrm{rate} \cdot (\frac{t_{\mathrm{dead}}}{t_{\mathrm{bin}}})) )}{\frac{\mathrm{rate}}{t_{\mathrm{bin}}}}

for paralyzable detectors, where

| :math:`N` = true count
| :math:`M` = measured count
| :math:`t_{\mathrm{dead}}` = dead time
| :math:`t_{\mathrm{bin}}` = TOF bin width
| :math:`\mathrm{rate}` = measured count rate
| :math:`\mathrm{W}` = `Lambert W function <https://en.wikipedia.org/wiki/Lambert_W_function>`_

The class ``SingleReadoutDeadTimeCorrection`` is a Mantid-style algorithm for computing the
dead-time correction for an event workspace. One can optionally include error events in the
dead-time computation.

Properties
----------

.. list-table::
   :widths: 20 20 20 20 20
   :header-rows: 1

   * - Name
     - Direction
     - Type
     - Default
     - Description
   * - InputWorkspace
     - Input
     - EventWorkspace
     - Mandatory
     - Input workspace used to compute dead-time correction
   * - InputErrorEventsWorkspace
     - Input
     - EventWorkspace
     -
     - Input workspace with error events used to compute dead-time correction
   * - DeadTime
     - Input
     - number
     - 4.2
     - Dead time in microseconds
   * - TOFStep
     - Input
     - number
     - 100.0
     - TOF bins to compute dead-time correction, in microseconds
   * - Paralyzable
     - Input
     - boolean
     - False
     - If True, paralyzable correction will be applied, non-paralyzable otherwise
   * - TOFRange
     - Input
     - dbl list
     - [0.0, 0.0]
     - TOF range to use to compute dead-time correction
   * - OutputWorkspace
     - Output
     - MatrixWorkspace
     - Mandatory
     - Output workspace containing the dead-time correction factor for each TOF bin

Usage
-----
Example using ``SingleReadoutDeadTimeCorrection`` (requires :any:`test-data` files)

.. testcode::

    import mantid.simpleapi as api
    import os
    import sys
    from pathlib import Path
    from quicknxs.interfaces.data_handling import DeadTimeCorrection
    from quicknxs.interfaces.data_handling.instrument import mantid_algorithm_exec
    # Load events
    path = Path().resolve().parent / "test" / "data" / "quicknxs-data" / "REF_M_42112.nxs.h5"
    path = path.as_posix()
    ws = api.LoadEventNexus(Filename=path, OutputWorkspace="raw_events")
    # Load error events
    err_ws = api.LoadErrorEventsNexus(path)
    # Compute dead-time correction
    tof_min = ws.getTofMin()
    tof_max = ws.getTofMax()
    corr_ws = mantid_algorithm_exec(
        DeadTimeCorrection.SingleReadoutDeadTimeCorrection,
        InputWorkspace=ws,
        InputErrorEventsWorkspace=err_ws,
        Paralyzable=False,
        DeadTime=4.2,
        TOFStep=100.0,
        TOFRange=[tof_min, tof_max],
        OutputWorkspace="corr",
    )
    # Apply dead-time correction
    ws = api.Multiply(ws, corr_ws, OutputWorkspace=str(ws))
