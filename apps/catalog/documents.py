from django.db.models import Avg
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

from apps.inventory.models import Stock
from apps.reviews.models import Review

from .models import Brand, Category, Product, Tag

# A small hand-picked synonym set so a search for "running shoes" also finds items only
# described as "sports shoes" or "joggers", etc. — a lightweight, dependency-free stand-in
# for full semantic/vector search (true embedding-based search can replace this later
# without changing the query-side API, since it's isolated to the index's analyzer here).
SYNONYM_GROUPS = [
    "shoes, sneakers, footwear, trainers",
    "running shoes, sports shoes, joggers, trainers",
    "laptop, notebook computer, notebook",
    "mobile, phone, smartphone, cellphone",
    "tv, television",
    "headphones, earphones, earbuds",
    "fridge, refrigerator",
    "washing machine, washer",
]


@registry.register_document
class ProductDocument(Document):
    name = fields.TextField(analyzer="synonym_analyzer", fields={"raw": fields.KeywordField()})
    description = fields.TextField(analyzer="synonym_analyzer")
    sku = fields.KeywordField()
    slug = fields.KeywordField()
    price = fields.FloatField()
    status = fields.KeywordField()
    product_type = fields.KeywordField()

    store_id = fields.IntegerField()
    store_name = fields.TextField(attr="store.name")

    category_name = fields.TextField(fields={"raw": fields.KeywordField()})
    category_slug = fields.KeywordField(attr="category.slug")

    brand_name = fields.TextField(fields={"raw": fields.KeywordField()})
    brand_slug = fields.KeywordField()

    tags = fields.KeywordField(multi=True)

    avg_rating = fields.FloatField()
    review_count = fields.IntegerField()
    is_available = fields.BooleanField()

    created_at = fields.DateField()

    class Index:
        name = "products"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "filter": {
                    "synonym_filter": {"type": "synonym", "synonyms": SYNONYM_GROUPS},
                },
                "analyzer": {
                    "synonym_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "synonym_filter"],
                    }
                },
            },
        }

    class Django:
        model = Product
        fields = []
        related_models = [Brand, Category, Tag, Review, Stock]

    def get_instances_from_related(self, related_instance):
        if isinstance(related_instance, Brand):
            return related_instance.products.all()
        if isinstance(related_instance, Category):
            return related_instance.products.all()
        if isinstance(related_instance, Tag):
            return related_instance.products.all()
        if isinstance(related_instance, Review):
            return related_instance.product
        if isinstance(related_instance, Stock):
            return related_instance.product

    def prepare_category_name(self, instance):
        return instance.category.name

    def prepare_brand_name(self, instance):
        return instance.brand.name if instance.brand else ""

    def prepare_brand_slug(self, instance):
        return instance.brand.slug if instance.brand else ""

    def prepare_tags(self, instance):
        return list(instance.tags.values_list("name", flat=True))

    def prepare_avg_rating(self, instance):
        return instance.reviews.aggregate(avg=Avg("rating"))["avg"] or 0.0

    def prepare_review_count(self, instance):
        return instance.reviews.count()

    def prepare_is_available(self, instance):
        return instance.stock_entries.with_available().filter(available__gt=0).exists()
