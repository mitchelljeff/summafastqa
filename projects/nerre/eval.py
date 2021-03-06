#!/usr/bin/python
# by Mattew Peters, who spotted that sklearn does macro averaging not micro averaging correctly and changed it

import os
from sklearn.metrics import precision_recall_fscore_support, cohen_kappa_score
import sys
import copy

def calculateMeasures(folder_gold="data/dev/", folder_pred="data_pred/dev/", remove_anno = "", ignoremissing=False):
    '''
    Calculate P, R, F1, Macro F
    :param folder_gold: folder containing gold standard .ann files
    :param folder_pred: folder containing prediction .ann files
    :param remove_anno: if set if "rel", relations will be ignored. Use this setting to only evaluate
    keyphrase boundary recognition and keyphrase classification. If set to "types", only keyphrase boundary recognition is evaluated.
    If set to "keys", only relations will be evaluated.
    :return:
    '''

    flist_gold = os.listdir(folder_gold)
    res_all_gold = []
    res_all_pred = []
    targets = []

    if type(remove_anno) == str:
        remove_anno = [remove_anno]
    if "types" in remove_anno:
        remove_anno.append("rel")

    for f in flist_gold:
        # ignoring non-.ann files, should there be any
        if not str(f).endswith(".ann"):
            continue
        f_gold = open(os.path.join(folder_gold, f), "r")
        try:
            f_pred = open(os.path.join(folder_pred, f), "r")
            res_full_pred, res_pred, spans_pred, rels_pred = normaliseAnnotations(f_pred, remove_anno)
        except IOError:
            if ignoremissing == True:
                continue
            print(f + " file missing in " + folder_pred + ". Assuming no predictions are available for this file.")
            res_full_pred, res_pred, spans_pred, rels_pred = [], [], [], []

        res_full_gold, res_gold, spans_gold, rels_gold = normaliseAnnotations(f_gold, remove_anno)

        spans_all = set(spans_gold + spans_pred)

        for i, r in enumerate(spans_all):
            if r in spans_gold:
                target = res_gold[spans_gold.index(r)].split(" ")[0]
                res_all_gold.append(target)
                if not target in targets:
                    targets.append(target)
            else:
                # those are the false positives, contained in pred but not gold
                res_all_gold.append("NONE")

            if r in spans_pred:
                target_pred = res_pred[spans_pred.index(r)].split(" ")[0]
                res_all_pred.append(target_pred)
            else:
                # those are the false negatives, contained in gold but not pred
                res_all_pred.append("NONE")

    if "keys" in remove_anno:
        targets = ["Hyponym-of", "Synonym-of"]
    #y_true, y_pred, labels, targets
    prec, recall, f1, support = precision_recall_fscore_support(
        res_all_gold, res_all_pred, labels=targets, average=None)
    # unpack the precision, recall, f1 and support
    metrics = {}
    for k, target in enumerate(targets):
        metrics[target] = {
            'precision': prec[k],
            'recall': recall[k],
            'f1-score': f1[k],
            'support': support[k]
        }

    # now micro-averaged
    if not "types" in remove_anno:
        prec, recall, f1, s = precision_recall_fscore_support(
            res_all_gold, res_all_pred, labels=targets, average='micro')
        metrics['overall'] = {
            'precision': prec,
            'recall': recall,
            'f1-score': f1,
            'support': sum(support)
        }
    else:
        # just binary classification, nothing to average
        metrics['overall'] = metrics['KEYPHRASE-NOTYPES']

    print_report(metrics, targets)
    return metrics



def calculateIAA(folder_gold="data/dev/", folder_pred="data_pred/dev/", ignoremissing=False):
    '''
    Calculate P, R, F1, Macro F
    :param folder_gold: folder containing gold standard .ann files
    :param folder_pred: folder containing prediction .ann files
    :param remove_anno: if set if "rel", relations will be ignored. Use this setting to only evaluate
    keyphrase boundary recognition and keyphrase classification. If set to "types", only keyphrase boundary recognition is evaluated.
    If set to "keys", only relations will be evaluated.
    :return:
    '''

    flist_gold = os.listdir(folder_gold)
    res_all_gold = []
    res_all_pred = []
    targets = []

    for f in flist_gold:
        # ignoring non-.ann files, should there be any
        if not str(f).endswith(".ann"):
            continue
        f_gold = open(os.path.join(folder_gold, f), "r")
        try:
            f_pred = open(os.path.join(folder_pred, f), "r")
            res_full_pred, res_pred, spans_pred, rels_pred = normaliseAnnotations(f_pred, remove_anno)
            # we don't want to measure empty documents, e.g. if participants gave up annotating
            if len(res_full_pred) == 0:
                print("Warning! Empty ones")
                continue
        except IOError:
            if ignoremissing == True:
                continue
            print(f + " file missing in " + folder_pred + ". Assuming no predictions are available for this file.")
            res_full_pred, res_pred, spans_pred, rels_pred = [], [], [], []

        res_full_gold, res_gold, spans_gold, rels_gold = normaliseAnnotations(f_gold, remove_anno)

        spans_all = set(spans_gold + spans_pred)

        for i, r in enumerate(spans_all):
            if r in spans_gold:
                target = res_gold[spans_gold.index(r)].split(" ")[0]
                res_all_gold.append(target)
                if not target in targets:
                    targets.append(target)
            else:
                # those are the false positives, contained in pred but not gold
                res_all_gold.append("NONE")

            if r in spans_pred:
                target_pred = res_pred[spans_pred.index(r)].split(" ")[0]
                res_all_pred.append(target_pred)
            else:
                # those are the false negatives, contained in gold but not pred
                res_all_pred.append("NONE")

    kappa = cohen_kappa_score(res_all_gold, res_all_pred)
    print("Cohen's kappa:", kappa)




def print_report(metrics, targets, digits=2):
    def _get_line(results, target, columns):
        line = [target]
        for column in columns[:-1]:
            line.append("{0:0.{1}f}".format(results[column], digits))
        line.append("%s" % results[columns[-1]])
        return line

    columns = ['precision', 'recall', 'f1-score', 'support']

    fmt = '%11s' + '%9s' * 4 + '\n'
    report = [fmt % tuple([''] + columns)]
    report.append('\n')
    for target in targets:
        results = metrics[target]
        line = _get_line(results, target, columns)
        report.append(fmt % tuple(line))
    report.append('\n')

    # overall
    line = _get_line(metrics['overall'], 'avg / total', columns)
    report.append(fmt % tuple(line))
    report.append('\n')

    print(''.join(report))


def normaliseAnnotations(file_anno, remove_anno):
    '''
    Parse annotations from the annotation files: remove relations (if requested), convert rel IDs to entity spans
    :param file_anno:
    :param remove_anno:
    :return:
    '''
    res_full_anno = []
    res_anno = []
    spans_anno = []
    rels_anno = []

    for l in file_anno:
        r_g = l.strip().split("\t")
        r_g_offs = r_g[1].split(" ")

        # remove relation instances if specified
        if "rel" in remove_anno and r_g_offs[0].endswith("-of"):
            continue

        res_full_anno.append(l.strip())
        # normalise relation instances by looking up entity spans for relation IDs
        if r_g_offs[0].endswith("-of"):
            arg1 = r_g_offs[1].replace("Arg1:", "")
            arg2 = r_g_offs[2].replace("Arg2:", "")
            for l in res_full_anno:
                r_g_tmp = l.strip().split("\t")
                if r_g_tmp[0] == arg1:
                    ent1 = r_g_tmp[1].replace(" ", "_")
                if r_g_tmp[0] == arg2:
                    ent2 = r_g_tmp[1].replace(" ", "_")

            if r_g_offs[0] == "Synonym-of":
                ent1_spl = ent1.split("_")
                ent2_spl = ent2.split("_")
                if ent1_spl[1] > ent2_spl[1]:
                    ent1_old = copy.copy(ent1)
                    ent1 = copy.copy(ent2)
                    ent2 = ent1_old

            spans_anno.append(" ".join([ent1, ent2]))
            res_anno.append(" ".join([r_g_offs[0], ent1, ent2]))
            rels_anno.append(" ".join([r_g_offs[0], ent1, ent2]))

        else:
            try:
                spans_anno.append(" ".join([r_g_offs[1], r_g_offs[2]]))
                keytype = r_g[1]
                if "types" in remove_anno:
                    keytype = "KEYPHRASE-NOTYPES"
                res_anno.append(keytype)
            except IndexError:
                print("IndexError! Faulty annotations")



    for r in rels_anno:
        r_offs = r.split(" ")
        # reorder hyponyms to start with smallest index
        if r_offs[0] == "Synonym-of" and r_offs[2].split("_")[1] < r_offs[1].split("_")[1]:  # 1, 2
            r = " ".join([r_offs[0], r_offs[2], r_offs[1]])

        # Check, in all other hyponym relations, if the synonymous entity with smallest index is used for them.
        # If not, change it so it is.
        if r_offs[0] == "Synonym-of":
            for r2 in rels_anno:
                r2_offs = r2.split(" ")
                if r2_offs[0] == "Hyponym-of" and r_offs[1] == r2_offs[1]:
                    r_new = " ".join([r2_offs[0], r_offs[2], r2_offs[2]])
                    try:
                        rels_anno[rels_anno.index(r2)] = r_new
                    except ValueError:
                        continue

                if r2_offs[0] == "Hyponym-of" and r_offs[1] == r2_offs[2]:
                    r_new = " ".join([r2_offs[0], r2_offs[1], r_offs[2]])
                    try:
                        rels_anno[rels_anno.index(r2)] = r_new
                    except ValueError:
                        continue

    rels_anno = list(set(rels_anno))

    res_full_anno_new = []
    res_anno_new = []
    spans_anno_new = []

    for r in res_full_anno:
        try:
            r_g = r.strip().split("\t")
            if r_g[0].startswith("R") or r_g[0] == "*":
                continue
            ind = res_full_anno.index(r)
            res_full_anno_new.append(r)
            res_anno_new.append(res_anno[ind])
            spans_anno_new.append(spans_anno[ind])
        except IndexError:
            print("IndexError! Faulty annotations")

    for r in rels_anno:
        res_full_anno_new.append("R\t" + r)
        res_anno_new.append(r)
        spans_anno_new.append(" ".join([r.split(" ")[1], r.split(" ")[2]]))

    return res_full_anno_new, res_anno_new, spans_anno_new, rels_anno


if __name__ == '__main__':
    folder_gold = "/Users/Isabelle/Documents/UCLMR/semeval_articles/test_final2/"#train_final2/"
    folder_pred = "/Users/Isabelle/Documents/UCLMR/semeval_articles/raw/anno21/"
    remove_anno = ""  # "", "rel" or "types"
    remove_from_macro = True
    if len(sys.argv) >= 2:
        folder_gold = sys.argv[1]
    if len(sys.argv) >= 3:
        folder_pred = sys.argv[2]
    if len(sys.argv) == 4:
        remove_anno = sys.argv[3]

    #calculateMeasures(folder_gold, folder_pred, remove_anno, remove_from_macro)

    calculateIAA(folder_gold, folder_pred, ignoremissing=True)
