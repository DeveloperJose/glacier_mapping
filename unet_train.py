#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 17 12:59:22 2021

@author: Aryal007
"""
from segmentation.data.data import fetch_loaders
from segmentation.model.frame import Framework
import segmentation.model.functions as fn

import yaml, json, pathlib, warnings, pdb, torch, logging, time, gc
from torch.utils.tensorboard import SummaryWriter
from addict import Dict
import numpy as np

warnings.filterwarnings("ignore")

if __name__ == "__main__":
    conf = Dict(yaml.safe_load(open('./conf/unet_train.yaml')))
    data_dir = pathlib.Path(conf.data_dir)
    class_name = conf.class_name
    run_name = conf.run_name
    #processed_dir = data_dir / "processed"
    processed_dir = data_dir
    train_loader, val_loader = fetch_loaders(processed_dir, conf.batch_size, conf.use_channels, val_folder = 'val')
    loss_fn = fn.get_loss(conf.model_opts.args.outchannels, conf.loss_opts)            
    frame = Framework(
        loss_fn = loss_fn,
        model_opts=conf.model_opts,
        optimizer_opts=conf.optim_opts,
        reg_opts=conf.reg_opts
    )

    if conf.fine_tune:
        fn.log(logging.INFO, f"Finetuning the model")
        run_name = conf.run_name+"_finetuned"
        model_path = f"{data_dir}/runs/{conf.run_name}/models/model_final.pt"
        if torch.cuda.is_available():
            state_dict = torch.load(model_path)
        else:
            state_dict = torch.load(model_path, map_location="cpu")
        frame.load_state_dict(state_dict)
        frame.freeze_layers()

    # Setup logging
    writer = SummaryWriter(f"{data_dir}/runs/{run_name}/logs/")
    writer.add_text("Configuration Parameters", json.dumps(conf))
    frame.add_graph(writer, next(iter(train_loader)))
    out_dir = f"{data_dir}/runs/{run_name}/models/"
    loss_val = np.inf
    
    fn.print_conf(conf)
    fn.log(logging.INFO, "# Training Instances = {}, # Validation Instances = {}".format(len(train_loader), len(val_loader)))

    for epoch in range(1, conf.epochs+1):
        # train loop
        loss_train, train_metric = fn.train_epoch(epoch, train_loader, frame, conf)
        fn.log_metrics(writer, train_metric, epoch, "train", conf.log_opts.mask_names)

        # validation loop
        #new_loss_val, val_metric = fn.validate(epoch, val_loader, frame, conf)
        #fn.log_metrics(writer, val_metric, epoch, "val", conf.log_opts.mask_names)
        new_loss_val = 0

        if (epoch-1) % 5 == 0:
            fn.log_images(writer, frame, train_loader, epoch, "train")
            fn.log_images(writer, frame, val_loader, epoch, "val")

        # Save best model
        if new_loss_val < float(loss_val):
            frame.save(out_dir, "best")

        loss_val = float(new_loss_val)
        writer.add_scalars("Loss", {"train": loss_train, "val": loss_val}, epoch)

        fn.print_metrics(conf, train_metric, train_metric)
        del(train_metric)
        del(loss_train)
        del(new_loss_val)
        torch.cuda.empty_cache()
        writer.flush()
        gc.collect()

    frame.save(out_dir, "final")
    writer.close()