.. _binning:

Binning a Reduced Workspace in QuickNXS
=======================================

Overview
--------

Binning is an essential process in reflectivity reduction within QuickNXS, organizing raw data into manageable intervals for accurate analysis.
There are two steps during which binning occurs:
1. An initial time-of-flight binning step to process the raw event data, which is later converted into Q bins (mandatory).
2. A final Q rebinning is optionally available for user who want their reflectivity output in specific Q binning.

This guide explains the available binning options in QuickNXS and how to configure them.

.. note:: All binning options are ultimately passed to the `MagnetismReflectometryReduction algorithm <https://docs.mantidproject.org/nightly/algorithms/MagnetismReflectometryReduction-v1.html>`_ in Mantid.

Binning Options
---------------

The following options allow users to fine-tune binning behavior:

**Bin Width** (Numeric Input, Applied Globally)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   - **Constraints:** Must be an integer value between 5 and 10000 microseconds.
   - **What It Does:** Defines the width, in microseconds, of bins used to rebin the input workspace in time-of-flight (TOF).
   - **How It Works:**

     - This step **always occurs** and cannot be skipped.
     - If the minimum TOF (Time-of-Flight) value is **≤ 0**, `Bin Width` is also used as the TOF minimum.
     - The direct beam workspace is rebinned to match the binning of the input workspace before reflectivity is calculated.

   - **How to Use It:** Enter a numeric value to specify the desired bin width.

   .. figure::
      ../images/bin_width.png
      :alt: Bin Width

      **Entering the Bin Width**


**Final Rebin** (Checkbox, Per-Run)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   - **What It Does:** Controls whether the final reduced workspace (converted to Q-space) undergoes additional rebinning.
   - **How It Works:**

     - When enabled, rebinning is performed using `Q Steps`, in units of 1/Å:

       - If **positive**, bins are evenly spaced.
       - If **negative**, bins are spaced logarithmically using a geometric progression.

     - This option is **only available** if `Constant-Q Binning` is **disabled**.
     - If `Constant-Q Binning` is enabled, it **takes priority** over `Final Rebin`.
     - If `Final Rebin` is enabled for a run, the `Q Steps` values can be viewed and updated in the reduction data table under the `Q-Steps` column.
     - The button `Apply final rebin to runs` applies final rebin with the same `Q Steps` value for all runs in the active reduction data table.

   - **How to Use It:** Check this box if you want to apply final rebinning for the active run, or use the button to apply final rebin for all runs.

   .. figure::
      ../images/final_rebin_button.png
      :alt: Apply Final Rebin to All Runs

      **Apply Final Rebin to All Runs in the Active Reduction Data Table**

   .. figure::
      ../images/final_rebin_per_run.png
      :alt: Final Rebin Per-Run Checkbox

      **Enabling Final Rebin Per-Run**


**Constant-Q Binning** (Checkbox, Applied Globally)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   - **What It Does:** uses the position of each pixel and the specified TOF binning to sum counts directly in Q bins. This differs from the traditional reflectivity calculation, which assumes that all counts in a TOF bin has the same Q value regardless of where they landed on the detector.
   - **How It Works:**

     - When enabled, `Final Rebin` is not performed.
     - Enabling Constant-Q binning changes the way R(q) is calculated.
     - `Q Steps` is used to determine binning:

       - If **positive**, bins are evenly spaced.
       - If **negative**, bins are spaced logarithmically using a geometric progression.

     - This setting is **global** and cannot be adjusted per-run.

   - **How to Use It:** Check this box if you want to maintain constant-Q binning. Ensure `Q Steps` is set appropriately for either linear or logarithmic binning.

   .. figure::
      ../images/constant_q_binning.png
      :alt: Constant-Q Binning

      **Enabling Constant-Q Binning**

**Q Steps** (Numeric Input, Per-Run or Global)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   - **Constraints:** Must be a floating point value between -0.1 and 0.1 units of 1/Å.
   - **What It Does:** Defines the bin width for the final rebinning in Q-space.
   - **How It Works:**

     - `Q Steps` is used in both `Final Rebin` and `Constant-Q Binning`.
     - When `Final Rebin` is enabled, `Q Steps` sets the bin width for the final rebinning.
     - When `Constant-Q Binning` is enabled, `Q Steps` determines whether binning follows a **linear** or **logarithmic** scale.

       - It controls the resolution of the final reduced workspace.
       - If `Q Steps` is **positive**, linear binning is applied with evenly spaced bins.
       - If `Q Steps` is **negative**, logarithmic binning is applied, where bin edges follow a geometric progression.

   - **How to Use It:** Enter a numeric value to specify the bin width for Q-space rebinning. Use negative values for logarithmic binning.

   .. figure::
      ../images/q_steps_global0.png
      :alt: Q Steps Global


   .. figure::
      ../images/q_steps_global1.png
      :alt: Q Steps Global

      **Setting Q Steps Globally disables the Q-Steps column in the reduction table**

   .. figure::
      ../images/q_steps_per_run0.png
      :alt: Q Steps Per-Run

   .. figure::
      ../images/q_steps_per_run1.png
      :alt: Q Steps Per-Run

      **Setting Q Steps Per-Run adds the value to the Q-Steps column in the reduction table**

Binning Workflow
----------------

To apply binning settings effectively, follow these steps:

1. **Set the Input Workspace Binning:**
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   - Enter a `Bin Width` value to define the initial binning.
   - If TOF min is ≤ 0, `Bin Width` will also be used as the TOF minimum.
   - The direct beam workspace is automatically rebinned to match this setting.

1. **Apply Final Binning (Optional):**
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   - If `Constant-Q Binning` is **enabled**, it takes priority over `Final Rebin`.
   - If `Constant-Q Binning` is **disabled** and additional Q-space binning is required, check `Final Rebin` and specify a `Q Steps` value.
   - If `Final Rebin` is enabled **per-run**, the `Q Steps` values can be viewed and updated in the reduction data table under the `Q-Steps` column.
   - If using `Constant-Q Binning`, ensure `Q Steps` is appropriately set for linear or logarithmic binning.

By adjusting these options, users can customize their reflectivity reduction workflow to achieve the desired data resolution and accuracy.
