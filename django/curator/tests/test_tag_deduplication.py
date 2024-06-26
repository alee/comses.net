import random
import shortuuid

from django.test import TestCase
from taggit.models import Tag

from curator.tag_deduplication import TagClusterer, TagGazetteer
from curator.models import CanonicalTag

random.seed(0)


def name_generator(unique_id, size=12):
    return shortuuid.uuid()[:size] + str(unique_id)


class TestTagClustering(TestCase):
    def setUp(self):
        tags = []
        for index in range(300):
            name = name_generator(index)
            tags.append(Tag(name=name, slug=name))
        Tag.objects.bulk_create(tags)

    def test_uncertain_pairs(self):
        tag_clustering = TagClusterer(clustering_threshold=0.5)
        uncertain_pairs = tag_clustering.uncertain_pairs()
        self.assertEqual(list, type(uncertain_pairs))
        self.assertLessEqual(1, len(uncertain_pairs))
        self.assertLessEqual(2, len(uncertain_pairs[0]))
        self.assertEqual(int, type(uncertain_pairs[0][0]["id"]))
        self.assertEqual(str, type(uncertain_pairs[0][0]["name"]))
        self.assertEqual(str, type(uncertain_pairs[0][0]["slug"]))

    def test_cluster_tags(self):
        clusters = self._cluster_tags()
        self.assertEqual(list, type(clusters))

        for cluster in clusters:
            self.assertLess(0, len(cluster))
            self.assertLess(0, len(cluster[0]))
            self.assertLess(0, len(cluster[1]))

    def _cluster_tags(self):
        tag_clustering = TagClusterer(clustering_threshold=0.5)
        return tag_clustering.cluster_tags()


class TestTagGazetteering(TestCase):
    def setUp(self):
        canonical_tags = []
        tags = []
        for index in range(300):
            name = name_generator(index)
            canonical_tags.append(CanonicalTag(name=name))
            tags.append(Tag(name=name + "a", slug=name + "a"))
            tags.append(Tag(name=name + "b", slug=name + "b"))
            tags.append(Tag(name=name + "c", slug=name + "c"))
        CanonicalTag.objects.bulk_create(canonical_tags)
        Tag.objects.bulk_create(tags)

    def test_uncertain_pairs(self):
        tag_clustering = TagGazetteer(search_threshold=0.5)
        uncertain_pairs = tag_clustering.uncertain_pairs()
        self.assertEqual(list, type(uncertain_pairs))
        self.assertEqual(1, len(uncertain_pairs))
        self.assertEqual(2, len(uncertain_pairs[0]))
        self.assertEqual(int, type(uncertain_pairs[0][0]["id"]))
        self.assertEqual(str, type(uncertain_pairs[0][0]["name"]))
        self.assertEqual(str, type(uncertain_pairs[0][0]["slug"]))

    def test_search(self):
        clusters = self._search()
        self.assertEqual(list, type(clusters))

        for cluster in clusters:
            self.assertEqual(int, type(cluster[0]))
            self.assertEqual(tuple, type(cluster[1]))

    def _search(self):
        tag_clustering = TagGazetteer(search_threshold=0.5)
        return tag_clustering.search({1: {"id": 1, "name": "abms"}})
