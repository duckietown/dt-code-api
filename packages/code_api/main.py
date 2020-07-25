import sys
from dt_class_utils import DTProcess, AppStatus

from code_api.api import CodeAPI
from code_api.jobs import UpdateCheckerWorker

CODE_API_PORT = 8086


class CodeAPIApp(DTProcess):
    
    def __init__(self):
        super(CodeAPIApp, self).__init__('CodeAPI')
        self._api = CodeAPI()
        self.status = AppStatus.RUNNING
        self._updates_checker = UpdateCheckerWorker()
        # register shutdown callback
        self.register_shutdown_callback(_kill)
        # launch updates checker thread
        self._updates_checker.start()
        # serve HTTP requests over the REST API
        self._api.run(host='0.0.0.0', port=CODE_API_PORT)


def _kill():
    sys.exit(0)


if __name__ == '__main__':
    app = CodeAPIApp()
