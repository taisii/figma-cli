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

