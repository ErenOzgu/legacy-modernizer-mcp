import urllib2

from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response


def home(request):
    prices = {}
    for key, value in prices.iteritems():
        print "price", key, value
    try:
        data = urllib2.urlopen("http://example.com").read()
    except IOError, e:
        raise ValueError, "cannot fetch"
    if request.user.is_authenticated():
        pass
    for i in xrange(10):
        pass
    return render_to_response("shop/list.html", {"data": unicode(data)})
