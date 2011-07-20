
from django.conf.urls.defaults import patterns

urlpatterns = patterns('repomgr.views',
    (r'^$', 'index'),
    (r'^(?P<repo_name>.+)$', 'detail')
)

