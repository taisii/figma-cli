import os

class FileIO:
    @staticmethod
    def read_all_logs(log_dir="logs"):
        all_logs_content = ""
        if not os.path.exists(log_dir):
            return all_logs_content

        for filename in sorted(os.listdir(log_dir)):
            if filename.endswith(".md"):
                with open(os.path.join(log_dir, filename), "r") as f:
                    all_logs_content += f.read() + "\n\n"
        return all_logs_content

    @staticmethod
    def read_recent_logs(log_dir="logs", num_logs=10):
        all_logs_content = ""
        if not os.path.exists(log_dir):
            return all_logs_content

        log_files = []
        for filename in os.listdir(log_dir):
            if filename.endswith(".md"):
                filepath = os.path.join(log_dir, filename)
                log_files.append((filepath, os.path.getmtime(filepath)))

        # Sort files by modification time, newest first
        log_files.sort(key=lambda x: x[1], reverse=True)

        # Read content of the most recent logs
        for i, (filepath, _) in enumerate(log_files):
            if i >= num_logs:
                break
            with open(filepath, "r") as f:
                all_logs_content += f.read() + "\n\n"
        return all_logs_content

