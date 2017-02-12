from __future__ import division, print_function
import matplotlib as mpl
mpl.use('Agg')
from collections import defaultdict
import sys
sys.path.insert(0,'.')  # need to import from base
from base.process import process
import numpy as np
from datetime import datetime, timedelta
from base.io_util import myopen
from seasonal_flu import *
import matplotlib.pyplot as plt
import seaborn as sns

mutations = {"h3n2": [('HA1', 170,'K'), ('HA1', 158,'F'), ('HA1', 158, 'S'),
                      ('HA1', 130, 'K'), ('HA1', 141, 'K')],
              "h1n1pdm": [('HA1', 161, 'N'), ('HA2', 173, 'E'), ('HA1', 182, 'P'), ('HA1', 214, 'G')]
                      }
region_colors = {r:col for r, col in zip(sorted(region_groups.keys()),
                                         sns.color_palette(n_colors=len(region_groups)))}

formats = ['png', 'svg', 'pdf']

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Process virus sequences, build tree, and prepare of web visualization')
    parser.add_argument('-y', '--years_back', type = str, default = 3, help='number of years back to sample')
    parser.add_argument('--resolution', type = str, help ="outfile suffix, can determine -v and -y")
    parser.add_argument('-r', '--raxml_time_limit', type = float, default = 1.0, help='number of hours raxml is run')
    parser.add_argument('-l', '--lineage', type = str, default = 'h3n2', help='flu lineage to process')
    params = parser.parse_args()
    params.time_interval = ["2014-01-01", "2017-02-01"]
    time_interval = [datetime.strptime(x, '%Y-%m-%d').date() for x in params.time_interval]
    input_data_path = '../fauna/data/'+params.lineage
    store_data_path = 'store/201702_report_'+ params.lineage
    build_data_path = 'build/201702_report_'+ params.lineage

    frequencies = {}
    ppy=12
    pivots = np.arange(time_interval[0].year+(time_interval[0].month-1)/12.0,
                       time_interval[1].year+time_interval[1].month/12.0, 1.0/ppy)

    flu = flu_process(input_data_path = input_data_path, store_data_path = store_data_path,
                   build_data_path = build_data_path, reference='flu/metadata/'+params.lineage+'_outgroup.gb',
                   proteins=['SigPep', 'HA1', 'HA2'],
                   method='SLSQP', inertia=np.exp(-1.0/ppy), stiffness=2.*ppy)
    age_dist={}
    for region, group in region_groups.iteritems():
        flu.load_sequences(fields={0:'strain', 2:'isolate_id', 3:'date', 4:'region',
                             5:'country', 7:"city", 8:"passage",9:'lab', 10:'age', 11:'gender'})
        flu.parse_age()
        flu.seqs.filter(lambda s:
                                (s.attributes['date']>=time_interval[0]
                                 and s.attributes['date']<time_interval[1]
                                 and (s.attributes['region'] in group or s.attributes['region']==group)))
        flu.seqs.filter(lambda s: len(s.seq)>=900)
        flu.seqs.filter(lambda s: s.name not in outliers[params.lineage])
        flu.subsample(10000, all_regions=False)
        flu.align()
        flu.estimate_mutation_frequencies(region="global", pivots=pivots, min_freq=0.2,
                                include_set = {'HA1':[x[1] for x in mutations[params.lineage]]})
#        import ipdb; ipdb.set_trace()
        frequencies[region] = (flu.mutation_frequencies, flu.mutation_frequency_confidence, flu.mutation_frequency_counts)
        flu.mutation_frequencies, flu.mutation_frequency_confidence, flu.mutation_frequency_counts = {}, {}, {}
        age_dist[region]={}
        plt.figure()
        for mi, (gene,pos, aa) in enumerate(mutations[params.lineage]):
            age_dist[region][(gene, pos, aa)] = ([x.attributes['age'] for x in flu.seqs.translations[gene]
                                                 if not np.isnan(x.attributes['age'])
                                                 and x.seq[pos]==aa],
                                                 [x.attributes['age'] for x in flu.seqs.translations[gene]
                                                 if not np.isnan(x.attributes['age'])
                                                 and x.seq[pos]!=aa])

            n_points = len(age_dist[region][(gene, pos, aa)][0])
            y, x = np.histogram(age_dist[region][(gene, pos, aa)][0],
                                bins=np.linspace(0,100,11), density=True)
            plt.plot(0.5*(x[1:]+x[:-1]), y, label="%s: %d%s, n=%d"%(gene, pos+1, aa, n_points))
        plt.title("region: "+region)
        plt.legend()
        plt.xlabel('age')
        plt.ylabel('density')
        for fmt in formats:
          plt.savefig(store_data_path+'_age_distribution_%s.%s'%(region,fmt))
        plt.close()

    age_dist['global'] =  defaultdict(list)
    for region, group in region_groups.iteritems():
        for mi, (gene,pos, aa) in enumerate(mutations[params.lineage]):
            age_dist['global'][(gene, pos, aa)].extend(age_dist[region][(gene, pos, aa)][0])

    plt.figure()
    for mi, (gene,pos, aa) in enumerate(mutations[params.lineage]):
        n_points = len(age_dist["global"][(gene, pos, aa)])
        y, x = np.histogram(age_dist["global"][(gene, pos, aa)],
                            bins=np.linspace(0,100,11), density=True)
        plt.plot(0.5*(x[1:]+x[:-1]), y, label="%s: %d%s, n=%d"%(gene, pos+1, aa, n_points))
    plt.title("global")
    plt.legend()
    plt.xlabel('age')
    plt.ylabel('density')
    for fmt in formats:
      plt.savefig(store_data_path+'_age_distribution_%s.%s'%("global",fmt))
    plt.close()


    # finally add a global sample
    flu.load_sequences(fields={0:'strain', 2:'isolate_id', 3:'date', 4:'region',
                         5:'country', 7:"city", 12:"subtype",13:'lineage'})
    flu.seqs.filter(lambda s:
                            (s.attributes['date']>=time_interval[0]
                             and s.attributes['date']<time_interval[1]))
    flu.seqs.filter(lambda s: len(s.seq)>=900)
    flu.seqs.filter(lambda s: s.name not in outliers[params.lineage])
    flu.subsample(30, all_regions=False)
    flu.align()
    flu.estimate_mutation_frequencies(region="global", pivots=pivots, min_freq=0.2,
                            include_set = {'HA1':[x[1] for x in mutations[params.lineage] if x[0]=='HA1'],
                                           'HA2':[x[1] for x in mutations[params.lineage] if x[0]=='HA2']})
    frequencies['global'] = (flu.mutation_frequencies, flu.mutation_frequency_confidence, flu.mutation_frequency_counts)
    flu.mutation_frequencies, flu.mutation_frequency_confidence, flu.mutation_frequency_counts = {}, {}, {}


    # plot frequency trajectories of selected mutations
    npanels = len(mutations[params.lineage])
    fig, axs = plt.subplots(npanels, 1, figsize=(8, 2+3*npanels), sharex=True)

    padding=2
    for mi, (gene,pos, aa) in enumerate(mutations[params.lineage]):
        axs[mi].text(2014, 0.8, '%s: %d%s'%(gene, pos+1, aa))
        axs[mi].set_ylim([0,1])
        axs[mi].set_xlim([2014,2017.8])
        axs[mi].ticklabel_format(useOffset=False)
        for region in sorted(region_groups.keys()):
            try:
                freq = frequencies[region][0][('global', gene)][(pos, aa)]
                conf = frequencies[region][1][('global', gene)][(pos, aa)]
                axs[mi].fill_between(pivots[:-padding], freq[:-padding]+conf[:-padding], freq[:-padding]-conf[:-padding],
                                     facecolor=region_colors[region], alpha=0.3)
                axs[mi].plot(pivots[:-padding], freq[:-padding], c=region_colors[region], label='%s'%(region), lw=3)
                axs[mi].plot(pivots[-padding-1:], freq[-padding-1:], c=region_colors[region], lw=3, ls=':')
                print("mutation", gene, pos, aa, "in", region)
            except:
                print("mutation", gene, pos, aa, "not found  in ", region)
        try:
            axs[mi].plot(pivots, frequencies["global"][0][('global', gene)][(pos, aa)],
                         c='k', label='global')
        except:
            print("mutation", gene, pos, aa, "not found globally")
        if mi==0:
          axs[mi].legend()
    for fmt in formats:
      plt.savefig(store_data_path+'_frequencies.'+fmt)
    plt.close()

    # make plot with total sequence count
    fig = plt.figure()
    ax = plt.subplot(111)
    for region in sorted(region_groups.keys()):
        ax.plot(pivots, frequencies[region][2]['global'],
                c=region_colors[region], label='%s'%(region))

    ax.legend()
    ax.set_ylabel("sequence count")
    ax.set_xlabel("year")
    ax.ticklabel_format(useOffset=False)
    for fmt in formats:
      plt.savefig(store_data_path+'_seq_count.'+fmt)
    plt.close()
