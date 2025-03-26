.. _advanced_parameters:

Advanced Parameters
===================

Advanced parameters are only configurable in the local configuration file
``~/.config/.quicknxs.conf``.

Q Parameters
------------



Reduction Parameters
--------------------

The following parameters are used in the reduction process:

 ======================= ========= ================================================
  Name                    Type      Description
 ======================= ========= ================================================
  email_send              boolean   Send email with results of reduction
  email_to                string    Email address(es) to send to (comma separated)
  email_subject           string    Email subject
  email_cc                string    Email CC
  email_send_data         boolean   Include data in email
  email_send_plots        boolean   Include plots in email
  email_zip_data          boolean   Zip data files
  export_asym             boolean   Export spin-asymmetry
  export_gisans           boolean   Export GISANS data
  export_offspec          boolean   Export raw off-specular data
  export_offspec_smooth   boolean   Export binned off-specular data
  export_specular         boolean   Export specular reflectivity
  format_5cols            boolean   Include theta column in output file(s)
  format_mantid           boolean   Export Mantid script
  format_matlab           boolean   Export Matlab file
  format_numpy            boolean   Export Numpy (.npz) file
  output_file_template    string    Output file naming template
 ======================= ========= ================================================
