from django.test import TestCase

from pulpcore.plugin.models import Artifact, Content, RemoteArtifact, ContentArtifact
from pulpcore.plugin.stages import (
    DeclarativeContent,
    DeclarativeArtifact,
    RemoteArtifactSaver,
)

from pulp_file.app.models import FileRemote


class RemoteArtifactSaverTestCase(TestCase):

    @staticmethod
    def url(remote, c_name, rel_path):
        return f'https://{remote.name}/{c_name}/{rel_path}'

    def setUp(self):
        """Setup 100 content instances with different (Remote)Artifact patterns."""
        self.remote1 = FileRemote.objects.create(name="remote1")
        self.remote2 = FileRemote.objects.create(name="remote2")
        self.remote3 = FileRemote.objects.create(name="remote3")

        self.d_cs = []
        for n in range(100):
            c_name = f'c{n:04d}'
            relative_path = 'artifact1'
            c = Content.objects.create()
            ca = ContentArtifact.objects.create(
                artifact=None, content=c, relative_path=relative_path
            )

            # Every third Content.artifact already has a matching RemoteArtifact
            if n % 3 == 0:
                RemoteArtifact.objects.create(
                    url=self.url(self.remote1, c_name, relative_path),
                    remote=self.remote1,
                    content_artifact=ca
                )
            # Every fifth Content.artifact has an non matching RemoteArtifact (different remote)
            if n % 5 == 0:
                RemoteArtifact.objects.create(
                    url=self.url(self.remote2, c_name, relative_path),
                    remote=self.remote2,
                    content_artifact=ca
                )

            d_a = DeclarativeArtifact(
                artifact=Artifact(),
                url=self.url(self.remote1, c_name, relative_path),
                relative_path=relative_path,
                remote=self.remote1,
            )

            d_as = [d_a]

            # Every seventh Content has an additional artifact. This Artifact
            # actually exists in the DB (should make no difference at all). For
            # every second of these, there is a matching RemoteArtifact using
            # remote3.
            if n % 7 == 0:
                relative_path2 = 'artifact2'
                a2 = Artifact.objects.create(
                    size=n, sha256=str(n), sha384=str(n), sha512=str(n)
                )
                ca2 = ContentArtifact.objects.create(
                    artifact=a2, content=c, relative_path=relative_path2
                )
                d_a2 = DeclarativeArtifact(
                    artifact=a2,
                    url=self.url(self.remote3, c_name, relative_path2),
                    relative_path=relative_path2,
                    remote=self.remote3,
                )
                d_as.append(d_a2)
                if n % 2 == 0:
                    RemoteArtifact.objects.create(
                        url=self.url(self.remote3, c_name, relative_path2),
                        remote=self.remote3,
                        content_artifact=ca2
                    )

            d_c = DeclarativeContent(c, d_artifacts=d_as)

            self.d_cs.append(d_c)

    def test_needed_remote_artifacts(self):
        stage = RemoteArtifactSaver()
        needed_urls = [ra.url for ra in stage._needed_remote_artifacts(self.d_cs)]

        expected_needed_urls = []
        for n in range(100):
            if n % 3:
                expected_needed_urls.append(self.url(self.remote1, f'c{n:04d}', 'artifact1'))
            if n % 7 == 0 and n % 2:
                expected_needed_urls.append(self.url(self.remote3, f'c{n:04d}', 'artifact2'))

        self.assertCountEqual(needed_urls, expected_needed_urls)

    def test_rel_path_change_raises(self):
        ContentArtifact.objects.create(
            artifact=None,
            content=self.d_cs[50].content,
            relative_path='no d_artifact for this path'
        )
        stage = RemoteArtifactSaver()
        with self.assertRaisesRegex(ValueError, r'no d_artifact for this path'):
            stage._needed_remote_artifacts(self.d_cs)
