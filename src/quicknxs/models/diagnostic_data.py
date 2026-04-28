import mantid.simpleapi as api

from quicknxs.utils.filepath import FilePath


class DiagnosticData(object):
    """Diagnostic data for a run or group of runs to help understand and debug issues with QuickNXS workspaces"""

    def __init__(self, file_path: str | list[str] | None = None, message: str | None = None, min_num_evts: int = 100):
        self.min_num_events = min_num_evts
        self.bad_files = set()
        self.file_path = None
        self.xs_list = []
        self.diagnostic_data = []
        self.sample_logs = []

        if file_path:
            self.file_path = FilePath(file_path)

            self.bad_files.add(self.file_path.split()[1])
            self.diagnostic_data = self._extract_diagnostic_data()
            self.sample_logs = self._get_sample_logs()

        if message is None:
            message = f"No valid cross-sections found in file: {file_path}"
        self.message = message

    def _extract_diagnostic_data(self):
        """Extract diagnostic information from workspaces.

        Returns
        -------
        list of dict
            List of dictionaries containing diagnostic information for each workspace.
        """
        diagnostic_data = []
        run_numbers = self.file_path.run_numbers()

        _xs_list = []
        path_dict = dict()

        for idx, path in enumerate(self.file_path.single_paths):
            _, fpath = FilePath(path).split()
            path_dict[run_numbers[idx]] = fpath
            ws_name = api.mtd.unique_hidden_name()
            ws = api.LoadEventNexus(Filename=path, OutputWorkspace=ws_name)
            ws.mutableRun().addProperty("run_number", run_numbers[idx], True)
            _xs_list.append(ws)

        self.xs_list = _xs_list

        for ws in self.xs_list:
            run = ws.getRun()

            def get_prop_value(run, prop_name, default="N/A"):
                if run.hasProperty(prop_name):
                    try:
                        prop = run.getProperty(prop_name)
                        if hasattr(prop, "getStatistics"):
                            return prop.getStatistics().mean
                        else:
                            return prop.value
                    except Exception:
                        return default
                return default

            data = {}

            run_number = get_prop_value(run, "run_number")
            xs_id = get_prop_value(run, "cross_section_id")
            if xs_id != "N/A":
                data["cross_section_id"] = f"Run {run_number} ({xs_id})"
            else:
                data["cross_section_id"] = f"Run {run_number}"

            event_count = ws.getNumberEvents()
            if event_count < self.min_num_events:
                self.bad_files.add(path_dict[run_number])
            data["event_count"] = event_count
            data["lambda_center"] = get_prop_value(run, "LambdaRequest")
            data["direct_pixel"] = get_prop_value(run, "DIRPIX")
            data["proton_charge"] = get_prop_value(run, "gd_prtn_chrg")
            sample_angle = get_prop_value(run, "SampleAngle")
            if sample_angle == "N/A":
                sample_angle = get_prop_value(run, "SANGLE")
            data["sample_angle"] = sample_angle
            data["dangle"] = get_prop_value(run, "DANGLE")
            data["dangle0"] = get_prop_value(run, "DANGLE0")
            counting_time = get_prop_value(run, "duration")
            data["counting_time"] = counting_time

            if counting_time != "N/A" and counting_time > 0:
                data["count_rate"] = event_count / counting_time
            else:
                data["count_rate"] = "N/A"

            diagnostic_data.append(data)

        return diagnostic_data

    def _get_sample_logs(self):
        """Extract all sample logs from workspaces.

        Returns
        -------
        list of dict
            List of dictionaries, each containing:
            - 'run_id': identifier for the run
            - 'logs': list of tuples (property_name, property_value)
        """
        sample_logs = []

        for ws in self.xs_list:
            run = ws.getRun()
            run_id = run.getProperty("run_number").value

            logs = []
            for prop in run.getProperties():
                logs.append((prop.name, str(prop.value)))
            logs = sorted(logs, key=lambda x: x[0])

            sample_logs.append({"run_id": run_id, "logs": logs})

        return sample_logs
