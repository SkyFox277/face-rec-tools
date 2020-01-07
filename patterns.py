#!/usr/bin/python3

import os
import re
import numpy
import shutil
import pickle
import piexif
import logging
import argparse
import collections
from imutils import paths

import log
import tools
import config


class Patterns(object):
    def __init__(self, folder, model='hog', max_size=1000,
                 num_jitters=1, encoding_model='large', train_classifer=False):
        self.__folder = folder
        self.__pickle_file = os.path.join(folder, 'patterns.pickle')
        self.__encodings = []
        self.__names = []
        self.__files = []
        self.__times = []
        self.__classifer = None
        self.__classes = []
        self.__model = model
        self.__encoding_model = encoding_model
        self.__max_size = int(max_size)
        self.__num_jitters = int(num_jitters)
        self.__train_classifer = train_classifer

    def generate(self, regenerate=False):
        import face_recognition

        logging.info(f'Patterns generation: {self.__folder} ({regenerate})')

        image_files = {}
        for image_file in list(paths.list_images(self.__folder)):
            image_files[image_file] = os.stat(image_file).st_mtime

        if not regenerate:
            self.load()
            filetimes = {f: t for f, t in zip(self.__files, self.__times)}
            filtered = {}
            for image_file in image_files:
                filename_exsists = image_file in filetimes
                if not filename_exsists or \
                        filetimes[image_file] != image_files[image_file]:
                    filtered[image_file] = image_files[image_file]
                    if filename_exsists:
                        self.__remove_file(image_file)

            if len(filtered) == 0:
                logging.info('Nothing changed')
                return

            image_files = filtered

        for (i, image_file) in enumerate(image_files):
            name = image_file.split(os.path.sep)[-2]
            logging.info(f'{i + 1}/{len(image_files)} file: {image_file}')

            exif = piexif.load(image_file)
            encoding = None
            try:
                encd = exif["0th"][piexif.ImageIFD.ImageDescription]
                encoding = pickle.loads(encd)['encoding']
                logging.debug(f'Loaded from Exif: {len(encoding)}')
            except Exception:
                pass

            if encoding is None:
                image = tools.read_image(image_file, self.__max_size)

                boxes = face_recognition.face_locations(
                    image, model=self.__model)
                if len(boxes) != 1:
                    logging.warning(
                        f'{len(boxes)} faces detected in {image_file}. Skip.')
                    continue
                encodings = face_recognition.face_encodings(
                    image, boxes, self.__num_jitters,
                    model=self.__encoding_model)
                encoding = encodings[0]

            self.__encodings.append(encoding)
            self.__names.append(name)
            self.__files.append(image_file)
            self.__times.append(image_files[image_file])

        self.__save()

    def __save(self):
        if self.__train_classifer:
            logging.info('Classification training')
            self.train_classifer()

        self.__persons = self.__calcPersons()

        logging.info('Patterns saving')
        data = {
            'names': self.__names,
            'files': self.__files,
            'encodings': self.__encodings,
            'times': self.__times,
            'persons': self.__persons,
            'classifer': self.__classifer,
            'classes': self.__classes}
        dump = pickle.dumps(data)

        with open(self.__pickle_file, 'wb') as f:
            f.write(dump)

        logging.info(
            f'Patterns done: {self.__pickle_file} ({len(dump)} bytes)')

    def __calc_out_filename(self, filename):
        out_filename = os.path.split(filename)[1]
        for n in self.__names:
            out_filename = re.sub(n + '_\d+_', '', out_filename)
            out_filename = re.sub(n + '_weak_\d+_', '', out_filename)
            out_filename = out_filename.replace(n, '')
        out_filename = re.sub('unknown_\d+_\d+_', '', out_filename)
        return out_filename

    def add_files(self, name, filenames, new=False, move=False):
        out_folder = os.path.join(self.__folder, name)
        if new:
            os.makedirs(out_folder, exist_ok=True)
        else:
            if not os.path.exists(out_folder):
                raise Exception(f"Name {name} not exists")
        for filename in filenames:
            out_filename = os.path.join(out_folder,
                                        self.__calc_out_filename(filename))
            logging.info(f'adding {filename} to {out_filename}')
            shutil.copyfile(filename, out_filename)
            if move:
                os.remove(filename)

    def add_file_data(self, name, filename, data):
        out_folder = os.path.join(self.__folder, name)
        os.makedirs(out_folder, exist_ok=True)
        out_filename = os.path.join(out_folder,
                                    self.__calc_out_filename(filename))
        logging.info(f'adding data of {filename} to {out_filename}')
        with open(out_filename, 'wb') as f:
            f.write(data)

    def __remove_file(self, filename):
        i = self.__files.index(filename)
        del self.__files[i]
        del self.__names[i]
        del self.__encodings[i]
        del self.__times[i]
        logging.debug(f'File removed: {filename}')

    def remove_files(self, filenames):
        self.load()
        for filename in filenames:
            self.__remove_file(filename)
            os.remove(filename)
        self.__save()

    def load(self):
        data = pickle.loads(open(self.__pickle_file, 'rb').read())
        self.__encodings = data['encodings']
        self.__names = data['names']
        self.__files = data['files']
        self.__times = data['times']
        self.__classifer = data['classifer']
        self.__classes = data['classes']
        self.__persons = data['persons']

    def optimize(self):
        import dlib

        encs = [dlib.vector(enc) for enc in self.__encodings]
        labels = dlib.chinese_whispers_clustering(encs, 0.1)
        uniq = {}
        to_remove = []
        for fname, label in zip(self.__files, labels):
            if label not in uniq:
                uniq[label] = fname
            else:
                name1 = fname.split(os.path.sep)[-2]
                name2 = uniq[label].split(os.path.sep)[-2]
                if name1 != name2:
                    logging.warning(
                        f'Different person {fname} {uniq[label]}')
                else:
                    to_remove.append(fname)

        self.remove_files(to_remove)
        logging.info(f'Optimized from {len(encs)} to {len(uniq)}.')

    def analyze(self):
        fset = {}
        for f in self.__files:
            filename = os.path.split(f)[1]
            if filename in fset:
                logging.warning(
                    f'Duplicate pattern file: {f} ({fset[filename]})')
            else:
                fset[filename] = f

    def __calcPersons(self):
        dct = collections.defaultdict(lambda: {'count': 0, 'image': 'Z'})
        for i, name in enumerate(self.__names):
            dct[name]['count'] += 1
            dct[name]['image'] = min(dct[name]['image'], self.__files[i])
        res = [{'name': k, 'count': v['count'], 'image': v['image']}
               for k, v in dct.items()]
        res.sort(key=lambda el: el['count'], reverse=True)
        return res

    def train_classifer(self):
        from sklearn import svm
        from sklearn import metrics
        from sklearn import preprocessing
        from sklearn import model_selection

        RANDOM_SEED = 42

        data = numpy.array(self.__encodings)
        le = preprocessing.LabelEncoder()
        labels = le.fit_transform(self.__names)

        (x_train, x_test, y_train, y_test) = model_selection.train_test_split(
            data,
            labels,
            test_size=0.20,
            random_state=RANDOM_SEED)

        skf = model_selection.StratifiedKFold(n_splits=5)
        cv = skf.split(x_train, y_train)

        Cs = [0.001, 0.01, 0.1, 1, 10, 100]
        gammas = [0.001, 0.01, 0.1, 1, 10, 100]
        param_grid = [
            {'C': Cs, 'kernel': ['linear']},
            {'C': Cs, 'gamma': gammas, 'kernel': ['rbf']}]

        init_est = svm.SVC(
            probability=True,
            class_weight='balanced',
            random_state=RANDOM_SEED)

        grid_search = model_selection.GridSearchCV(
            estimator=init_est,
            param_grid=param_grid,
            n_jobs=4,
            cv=cv)

        grid_search.fit(x_train, y_train)

        self.__classifer = grid_search.best_estimator_
        self.__classes = list(le.classes_)

        y_pred = self.__classifer.predict(x_test)

        logging.info('Confusion matrix \n' +
                     str(metrics.confusion_matrix(y_test, y_pred)))

        logging.info('Classification report \n' +
                     str(metrics.classification_report(
                         y_test, y_pred, target_names=self.__classes)))

    def classifer(self):
        return self.__classifer

    def classes(self):
        return self.__classes

    def encodings(self):
        return self.__encodings

    def names(self):
        return self.__names

    def files(self):
        return self.__files

    def persons(self):
        return self.__persons


def args_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-a', '--action', help='Action', required=True,
        choices=['gen',
                 'add',
                 'add_new',
                 'add_gen',
                 'remove',
                 'list',
                 'persons',
                 'optimize',
                 'analyze'])
    parser.add_argument('-p', '--patterns', help='Patterns file')
    parser.add_argument('-l', '--logfile', help='Log file')
    parser.add_argument('-n', '--name', help='Person name')
    parser.add_argument('files', nargs='*', help='Files with one face')
    parser.add_argument('-r', '--regenerate', help='Regenerate all',
                        action='store_true')
    parser.add_argument('-c', '--config', help='Config file')
    return parser.parse_args()


def main():
    args = args_parse()
    cfg = config.Config(args.config)
    log.initLogger(args.logfile)

    patt = Patterns(cfg.get_def('main', 'patterns', args.patterns),
                    model=cfg['main']['model'],
                    max_size=cfg['main']['max_image_size'],
                    num_jitters=cfg['main']['num_jitters'],
                    encoding_model=cfg['main']['encoding_model'])

    if args.action == 'gen':
        patt.generate(args.regenerate)
    elif args.action == 'add':
        patt.load()
        patt.add_files(args.name, args.files)
    elif args.action == 'add_new':
        patt.load()
        patt.add_files(args.name, args.files, True)
    elif args.action == 'add_gen':
        patt.load()
        patt.add_files(args.name, args.files)
        patt.generate(args.regenerate)
    elif args.action == 'remove':
        patt.remove_files(args.files)
    elif args.action == 'list':
        patt.load()
        for name, filename in zip(patt.names(), patt.files()):
            print(name, filename)
    elif args.action == 'persons':
        patt.load()
        for p in patt.persons():
            print(p)
    elif args.action == 'optimize':
        patt.load()
        patt.optimize()
    elif args.action == 'analyze':
        patt.load()
        patt.analyze()


if __name__ == '__main__':
    main()
