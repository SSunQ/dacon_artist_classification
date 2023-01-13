import os
import argparse
import multiprocessing
from importlib import import_module
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm
import warnings
from dataset import get_dataset
from utils import seed_everything, competition_metric, \
                save_model, increment_path


def train(model, optimizer, train_loader, test_loader, scheduler,
          device, saved_dir, args):

    model.to(device)

    criterion = nn.CrossEntropyLoss().to(device)

    best_score = 0

    for epoch in range(1, args.epochs + 1):

        model.train()
        train_loss = []

        for img, label in tqdm(iter(train_loader)):
            img, label = img.float().to(device), label.to(device)

            optimizer.zero_grad()

            model_pred = model(img)

            loss = criterion(model_pred, label)

            loss.backward()
            optimizer.step()

            train_loss.append(loss.item())

        tr_loss = np.mean(train_loss)

        val_loss, val_score = validation(model, criterion, test_loader, device)

        print(f'Epoch [{epoch}], Train Loss : [{tr_loss:.5f}] Val Loss : [{val_loss:.5f}] Val F1 Score : [{val_score:.5f}]')

        if scheduler is not None:
            scheduler.step()

        if best_score < val_score:
            best_score = val_score

            file_name = f'{args.model}_Epoch_{epoch}_F1_{best_score:.5f}'
            save_model(model, saved_dir, file_name)


def validation(model, criterion, test_loader, device):
    model.eval()

    model_preds = []
    true_labels = []

    val_loss = []

    with torch.no_grad():
        for img, label in tqdm(iter(test_loader)):
            img, label = img.float().to(device), label.to(device)

            model_pred = model(img)

            loss = criterion(model_pred, label)

            val_loss.append(loss.item())

            model_preds += model_pred.argmax(1).detach().cpu().numpy().tolist()
            true_labels += label.detach().cpu().numpy().tolist()

    val_f1 = competition_metric(true_labels, model_preds)
    return np.mean(val_loss), val_f1


def parse_arg():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('--data_dir', type=str, default='data/')
    parser.add_argument('--model', type=str, default='BaseModel')
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--lr', type=float, default=3e-4)
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--seed', type=int, default=41)
    parser.add_argument('--name', type=str, default='exp', help='model save at {name}')
    args = parser.parse_args()
    return args


if __name__ == "__main__":

    args = parse_arg()
    print(args)

    warnings.filterwarnings('ignore')

    device = "cuda" if torch.cuda.is_available() else "cpu"

    saved_dir = increment_path(os.path.join('./output/model', args.name))

    seed_everything(args.seed)

    num_workers = multiprocessing.cpu_count() // 2

    # Dataset
    train_dataset, val_dataset = get_dataset(args)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size,
                              shuffle=True, num_workers=num_workers)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size,
                            shuffle=False, num_workers=num_workers)

    # Train model
    model_module = getattr(import_module("model"), args.model)
    model = model_module(num_classes=50)
    model.eval()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = None
    train(model, optimizer, train_loader, val_loader, scheduler,
          device, saved_dir, args)
