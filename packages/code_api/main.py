import sys
from dt_class_utils import DTProcess, AppStatus

from code_api.api import CodeAPI

CODE_API_PORT = 8086


class CodeAPIApp(DTProcess):
    
    def __init__(self):
        super(CodeAPIApp, self).__init__('CodeAPI')
        self._api = CodeAPI()
        self.register_shutdown_callback(_kill)
        self.status = AppStatus.RUNNING
        self._api.run(host='0.0.0.0', port=CODE_API_PORT)


def _kill():
    sys.exit(0)


if __name__ == '__main__':
    app = CodeAPIApp()
