from setuptools import setup
setup(name='face-rec-tools',
      version='1.0.0',
      description='Face Recognition Tools',
      author='Alexander Bushnev',
      author_email='Alexander@Bushnev.ru',
      license='GNU General Public License v3.0',
      packages=['face_rec_tools'],
      python_requires='>=3.6',
      data_files=[('/etc/face-rec-tools/', ['cfg/frontal.cfg',
                                            'cfg/full.cfg']),
                  ('/usr/share/face-rec-tools/web/', ['web/index.html',
                                                      'web/pattlink.png',
                                                      'web/srclink.png',
                                                      'web/style.css'])],
      scripts=['face-rec-cli',
               'face-rec-server',
               'face-rec-patterns',
               'face-rec-plexsync'],
      zip_safe=False)
