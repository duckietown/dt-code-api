from flask import Blueprint

from code_api.utils import response_ok, dt_label
from code_api.knowledge_base import KnowledgeBase


info = Blueprint('modules_info', __name__)
__all__ = ['info']


@info.route('/modules/info')
def _info():
    # return current status
    data = {}
    for tag, module in KnowledgeBase.get('modules'):
        data[tag] = labels_to_dict(module.labels())
    return response_ok(data)


def labels_to_dict(labels: dict) -> dict:
    data = {}
    domain = dt_label('')
    for label, value in labels.items():
        cur = data
        ns = label[len(domain):].split('.')
        for step in ns[:-1]:
            if step not in cur:
                cur[step] = {}
            cur = cur[step]
        cur[ns[-1]] = value
    return data
