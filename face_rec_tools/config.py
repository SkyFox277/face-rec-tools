#!/usr/bin/python3

import os
import configparser


class Config(object):
    DEFAULT_CONFIG_FILE = os.path.expanduser('~/.face-rec.cfg')
    DEFAULTS = {
        'recognition': {
            'model': 'cnn',
            'encoding_model': 'large',
            'distance_metric': 'default',
            'num_jitters': 100,
            'threshold': 0.3,
            'threshold_weak': 0.35,
            'threshold_clusterize': 0.4,
            'threshold_equal': 0.17,
            'min_face_size': 20,  # pixels
            'max_face_profile_angle': 90,  # degries
            'min_video_face_count': 3,
        },
        'processing': {
            'max_image_size': 1000,
            'debug_out_image_size': 100,
            'max_video_frames': 3600,  # 2 min
            'video_frames_step': 10,
            'video_batch_size': 8,
            'max_workers': 2,
            'cuda_memory_limit': 1536,  # MB
        },
        'files': {
            'db': 'face-rec/rec.db',
            'cachedb': 'face-rec/cache.db',
            'patterns': 'face-rec/patterns/',
            'nomedia_files': '.plexignore:.nomedia',
        },
        'server': {
            'port': 8081,
            'web_path': 'web',
            'face_cache_path': '/tmp/facereccache/',
            'log_file': 'face-rec/face-rec-server.log',
        },
        'plex': {
            'db': '/opt/plexmediaserver/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db',  # noqa
            'folders': '~/Pictures:~/Videos'  # noqa
        }
    }

    def __init__(self, filename=None, create=False):
        if filename is None:
            filename = self.DEFAULT_CONFIG_FILE

        self.__config = configparser.ConfigParser()
        self.__config.read_dict(self.DEFAULTS)
        self.__config.read([filename, ])
        self.__filename = filename

        if create:
            self.__create_if_not_exists()

    def __create_if_not_exists(self):
        if os.path.exists(self.DEFAULT_CONFIG_FILE):
            return

        with open(self.DEFAULT_CONFIG_FILE, 'w') as conffile:
            self.__config.write(conffile)

    def __getitem__(self, sect):
        return self.__config[sect]

    def get_def(self, sect, name, default):
        if default is not None:
            return default

        return self.__config[sect][name]

    def get_data_path(self, sect, name):
        path = self.__config[sect][name]
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(
                os.path.abspath(__file__)), path)
        return path

    def get_path(self, sect, name):
        path = self.__config[sect][name]
        res = [os.path.expanduser(f) for f in path.split(':')]
        if len(res) == 1:
            return res[0]
        return res

    def filename(self):
        return self.__filename


if __name__ == "__main__":
    Config(create=True)
