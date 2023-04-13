#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 24 13:27:56 2021

@author: Aryal007
"""
from utils import istarmap
import os, yaml, warnings, random, pdb, multiprocessing
from pathlib import Path
import numpy as np
from addict import Dict
import segmentation.data.slice as fn
import pandas as pd

from tqdm import tqdm

if __name__ == '__main__':
    random.seed(42)
    np.random.seed(42)
    warnings.filterwarnings("ignore")

    conf = Dict(yaml.safe_load(open('./conf/slice_and_preprocess.yaml')))

    saved_df = pd.DataFrame(columns=["Landsat ID", "Image", "Slice", "Background",
                                    "Clean Ice", "Debris", "Masked", "Background Percentage",
                                    "Clean Ice Percentage", "Debris Percentage",
                                    "Masked Percentage", "split"])

    images = sorted(os.listdir(Path(conf.image_dir)))
    idx = np.random.permutation(len(images))
    splits = {
        'test'  : sorted([images[i] for i in idx[:int(conf.test*len(images))]]),
        'val'   : sorted([images[i] for i in idx[int(conf.test*len(images)):int((conf.test+conf.val)*len(images))]]),
        'train' : sorted([images[i] for i in idx[int((conf.test+conf.val)*len(images)):]])
    }
    labels = fn.read_shp(Path(conf.labels_dir) / "HKH_CIDC_5basins_all.shp")
    fn.remove_and_create(conf.out_dir)

    pbar = tqdm(total=1, desc='...')

    def process(i, _filename):
        global saved_df, conf, pbar
        filename = Path(conf.image_dir) / _filename
        dem_filename = Path(conf.dem_dir) / _filename
        # print(f"Filename: {filename.name}")
        tiff = fn.read_tiff(filename)
        dem = fn.read_tiff(dem_filename)
        mask = fn.get_mask(tiff, labels)
        mean, std, _min, _max, saved_df = fn.save_slices(filename.name, i, tiff, dem, mask, savepath, saved_df, pbar, **conf)
        return mean, std, _min, _max

    for split, meta in splits.items():
        means, stds, mins, maxs = [], [], [], []
        savepath = Path(conf["out_dir"]) / split
        fn.remove_and_create(savepath)

        pbar.set_description(f'Processing dataset {split}')
        pbar.reset(len(meta))
        with multiprocessing.Pool(32) as pool:
            for result in pool.istarmap(process, enumerate(meta)):
                mu, s, mi, ma = result
                means.append(mu)
                stds.append(s)
                mins.append(mi)
                maxs.append(ma)

                pbar.update(1)

    pbar.close()

        # for i, _filename in enumerate(meta):
        #     filename = Path(conf.image_dir) / _filename
        #     dem_filename = Path(conf.dem_dir) / _filename
        #     print(f"Filename: {filename.name}")
        #     tiff = fn.read_tiff(filename)
        #     dem = fn.read_tiff(dem_filename)
        #     mask = fn.get_mask(tiff, labels)
        #     mean, std, _min, _max, saved_df = fn.save_slices(
        #     filename.name, i, tiff, dem, mask, savepath, saved_df, **conf)
        #     means.append(mean)
        #     stds.append(std)
        #     mins.append(_min)
        #     maxs.append(_max)
    means = np.mean(np.asarray(means), axis=0)
    stds = np.mean(np.asarray(stds), axis=0)
    mins = np.min(np.asarray(mins), axis=0)
    maxs = np.max(np.asarray(maxs), axis=0)
    np.save(conf.out_dir + f"normalize_{split}", np.asarray((means, stds, mins, maxs)))

    saved_df.to_csv(conf.out_dir + "slice_meta.csv", encoding='utf-8', index=False)
    print("Saving slices completed!!!")