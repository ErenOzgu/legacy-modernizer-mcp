from django.db import models
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class Customer(models.Model):
    name = models.CharField(max_length=100)

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ("customer_detail", [self.pk])


class Order(models.Model):
    customer = models.ForeignKey(Customer)
    parent = models.ForeignKey(
        "self",
        null=True,
    )
    shipped_by = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="+")
    reviewer = models.OneToOneField(Customer, models.SET_NULL, null=True)
