"""Cloudinary storage for existing Django ImageFields; no database conversion."""
import hashlib
import re
from pathlib import PurePosixPath
from tempfile import SpooledTemporaryFile
from urllib.request import urlopen

import cloudinary.api
import cloudinary.uploader
from cloudinary.exceptions import NotFound
from cloudinary.utils import cloudinary_url
from django.core.files import File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


def digest_file(handle):
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()


@deconstructible
class CloudinaryMediaStorage(Storage):
    """Public original images, immutable asset IDs, explicit per-instance credentials."""

    def __init__(self, cloud_name, api_key, api_secret, prefix='gadgetflow/media'):
        self.cloud_name = cloud_name
        self.api_key = api_key
        self.api_secret = api_secret
        self.prefix = prefix.strip('/')
        if (not self.prefix or len(self.prefix) > 150
                or not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', self.prefix)
                or any(re.fullmatch(r'v\d+', part) for part in self.prefix.split('/'))):
            raise ValueError('CLOUDINARY_MEDIA_PREFIX must be a safe nonempty folder prefix, at most 150 characters.')

    @property
    def credentials(self):
        return {'cloud_name': self.cloud_name, 'api_key': self.api_key, 'api_secret': self.api_secret}

    def public_id(self, name):
        name = str(name)
        if (not name or '\\' in name or PurePosixPath(name).is_absolute()
                or any(part in {'', '.', '..'} for part in name.split('/'))):
            raise ValueError('Unsafe media filename')
        # Include the entire exact key, including its extension, in the hash.
        # foo.jpg and foo.png cannot alias each other, and legacy ImageField
        # strings never need to become provider-specific public IDs.
        return self.prefix + '/' + hashlib.sha256(name.encode('utf-8')).hexdigest()

    def _delivery_url(self, name, version=None):
        options = {'cloud_name': self.cloud_name, 'secure': True,
                   'resource_type': 'image', 'type': 'upload'}
        if version:
            options['version'] = version
        return cloudinary_url(self.public_id(name), **options)[0]

    def url(self, name):
        # No API lookup or volatile local manifest is needed to render a page.
        return self._delivery_url(name)

    def _resource(self, name):
        return cloudinary.api.resource(self.public_id(name), resource_type='image',
                                       type='upload', **self.credentials)

    def exists(self, name):
        try:
            # Django's alternate-name loop uses os.path.join on Windows.
            self._resource(str(name).replace('\\', '/'))
        except NotFound:
            return False
        return True

    def size(self, name):
        return self._resource(name)['bytes']

    def _read_original(self, name, version=None):
        temporary = SpooledTemporaryFile(max_size=8 * 1024 * 1024)
        try:
            with urlopen(self._delivery_url(name, version), timeout=30) as response:
                if response.status != 200 or not response.headers.get('Content-Type', '').startswith('image/'):
                    raise OSError('Cloudinary did not return an image with HTTP 200')
                for block in iter(lambda: response.read(1024 * 1024), b''):
                    temporary.write(block)
            temporary.seek(0)
            return File(temporary, name=name)
        except Exception:
            temporary.close()
            raise

    def _open(self, name, mode='rb'):
        if mode not in {'rb', 'r'}:
            raise ValueError('Cloudinary originals are read-only; use Storage.save for new uploads')
        return self._read_original(name)

    def _upload(self, name, content, digest):
        content.seek(0)
        result = cloudinary.uploader.upload(
            content, public_id=self.public_id(name), resource_type='image', type='upload',
            overwrite=False, unique_filename=False, use_filename=False,
            context={'django_path': str(name), 'original_sha256': digest},
            **self.credentials,
        )
        if result.get('public_id') != self.public_id(name):
            raise OSError('Cloudinary returned an unexpected asset ID; database filename unchanged')
        return result

    def _save(self, name, content):
        name = str(name).replace('\\', '/')
        content.seek(0)
        digest = digest_file(content)
        result = self._upload(name, content, digest)
        if result.get('existing'):
            # A concurrent upload may have claimed the name after exists().
            # Never attach an Admin upload to someone else's bytes.
            raise FileExistsError('Media key already exists; choose another filename')
        with self._read_original(name, result.get('version')) as uploaded:
            if digest_file(uploaded) != digest:
                raise OSError('Uploaded original verification failed; database filename unchanged')
        return name

    def transfer_original(self, name, content, digest):
        """Exact-name transfer: never rename a key, overwrite, delete, or write DB rows."""
        result = self._upload(name, content, digest)
        with self._read_original(name, result.get('version')) as original:
            identical = digest_file(original) == digest
        if result.get('existing'):
            return 'existing_identical' if identical else 'conflict_not_overwritten'
        return 'uploaded' if identical else 'uploaded_bytes_mismatch'

    # Deliberately no delete(): changing/clearing an ImageField must not remove
    # preserved originals. Provider-side cleanup is a separate explicit action.
