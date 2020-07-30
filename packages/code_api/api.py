from flask import Flask
from flask_cors import CORS

from .actions.version import version
from .actions.info import info
from .actions.status import status
from .actions.update import update


class CodeAPI(Flask):

    def __init__(self):
        super(CodeAPI, self).__init__(__name__)
        # register blueprints
        self.register_blueprint(version)
        self.register_blueprint(info)
        self.register_blueprint(status)
        self.register_blueprint(update)
        # apply CORS settings
        CORS(self)
