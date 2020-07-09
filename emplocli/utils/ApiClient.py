import re
from xmlrpc.client import ServerProxy

class ApiClient:
    def __init__(self, url):
        self.url = url

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, url):
        regex = re.compile("http[s]?://([a-zA-z0-9].*.)?[a-zA-z0-9].*.[a-zA-z].*.*[^/]$")
        if regex.match(url):
            self._url = url
            self.common = ServerProxy("{}/xmlrpc/2/common".format(self.url))
            self.models = ServerProxy("{}/xmlrpc/2/object".format(self.url))
        else:
            raise ValueError("Invalid URL: \"%s\".", url)

    @url.deleter
    def url(self):
        del self._url

    def authenticate(self, db, username, password):
        return self.common.authenticate(db, username, password, {})
        
    def search_read(self, db, uid, password, model, field, domain=None):
        return self.models.execute_kw(db, uid, password, model, "search_read", [[[domain["field_name"], domain["operator"], domain["value"]]] if domain is not None else []], {"fields": [field]})

    def attendance_manual(self, db, uid, password, employee_id):
        return self.models.execute_kw(db, uid, password, "hr.employee", "attendance_manual", [employee_id, False])

    def write(self, db, uid, password, model, record, field, value):
        return self.models.execute_kw(db, uid, password, model, "write", [[record], {field: value}])

