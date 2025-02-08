import seaborn as sns
import matplotlib.pyplot as plt
import pickle
import json
import os
import pandas as pd
from os.path import join as opj

VIZ_DIR ="/Users/anushreechaudhuri/pCloud Drive/MIT/MIT Work/Renewable Energy UROP/dispute-characterization/visualizations"

CB91_Blue = '#2CBDFE'
CB91_Green = '#47DBCD'
CB91_Pink = '#F3A0F2'
CB91_Purple = '#9D2EC5'
CB91_Violet = '#661D98'
CB91_Amber = '#F5B14C'

color_list = [CB91_Blue, CB91_Pink, CB91_Green, CB91_Amber,
            CB91_Purple, CB91_Violet]
plt.rcParams['axes.prop_cycle'] = plt.cycler(color=color_list)

CB91_Grad_BP = ['#2cbdfe', '#2fb9fc', '#33b4fa', '#36b0f8',
                '#3aacf6', '#3da8f4', '#41a3f2', '#449ff0',
                '#489bee', '#4b97ec', '#4f92ea', '#528ee8',
                '#568ae6', '#5986e4', '#5c81e2', '#607de0',
                '#6379de', '#6775dc', '#6a70da', '#6e6cd8',
                '#7168d7', '#7564d5', '#785fd3', '#7c5bd1',
                '#7f57cf', '#8353cd', '#864ecb', '#894ac9',
                '#8d46c7', '#9042c5', '#943dc3', '#9739c1',
                '#9b35bf', '#9e31bd', '#a22cbb', '#a528b9',
                '#a924b7', '#ac20b5', '#b01bb3', '#b317b1']
sns.set(font='Arial',
        rc={
'axes.axisbelow': False,
'axes.edgecolor': 'lightgrey',
'axes.facecolor': 'None',
'axes.labelcolor': 'dimgrey',
'axes.spines.right': False,
'axes.spines.top': False,
'figure.facecolor': 'white',
'lines.solid_capstyle': 'round',
'patch.edgecolor': 'w',
'patch.force_edgecolor': True,
'text.color': 'dimgrey',
'xtick.bottom': False,
'xtick.color': 'dimgrey',
'xtick.direction': 'out',
'xtick.top': False,
'ytick.color': 'dimgrey',
'ytick.direction': 'out',
'ytick.left': False,
'ytick.right': False})
sns.set_context("notebook", rc={"font.size":16,
                                "axes.titlesize":20,
                                "axes.labelsize":18})
sns.set_style("whitegrid", {'axes.grid' : False})


def compute_avg_relevance():
    def calculate_avg_score(plant_code):
        path = f"results/article_relevance/{plant_code}.json"

        if not os.path.exists(path):
            return None

        with open(path, "r") as f:
            relevance_data = json.load(f)

        try:
            if relevance_data == []:
                return None
            scores = [item['grade'] for item in relevance_data.get('scores_and_justifications', [])]
        except:
            print(plant_code)
            print(scores)

        if scores:
            return sum(scores) / len(scores)
        else:
            return None

    joined_data['avg_relevance_score'] = joined_data['plant_code'].apply(calculate_avg_score)
    joined_data['avg_relevance_score'] = pd.to_numeric(joined_data['avg_relevance_score'], errors='coerce')
    return joined_data



# Plotting the distribution of average relevance scores
def plot_avg_relevance_score_distribution(joined_data):
    plt.figure(figsize=(10, 6))
    sns.set(font_scale=1.2)
    sns.set_style("whitegrid")
    plt.grid(False)
    ax = sns.distplot(joined_data['avg_relevance_score'].dropna(), bins=20, kde=True)
    ax.set_title('Distribution of Average Relevance Scores')
    ax.set_xlabel('Average Relevance Score')
    ax.set_ylabel('Frequency')
    plt.savefig(opj(VIZ_DIR, "avg_relevance_score_distribution.jpg"))


# # Plotting scatter plot of avg_relevance_score vs. "capacity"
# import numpy as np
# from scipy.stats import pearsonr

# # Prepare the data
# x = joined_data['avg_relevance_score'].dropna()
# y = joined_data.loc[x.index, 'capacity']

# # Calculate the correlation coefficient
# correlation_coef, _ = pearsonr(x, y)

# # Create the jointplot
# g = sns.jointplot(x='avg_relevance_score', y='capacity', data=joined_data, kind='scatter', height=8, ratio=5, space=0.2, alpha=0.5)
# g.ax_joint.set_yscale('log')

# # Enhance the plot with titles and labels
# plt.suptitle('Scatter Plot of Capacity (MW) vs. Average Relevance Score', fontsize=15, fontname='Arial', y=1.02)
# plt.xlabel('Average Relevance Score', fontsize=12, fontname='Arial')
# plt.ylabel('Capacity (MW)', fontsize=12, fontname='Arial')
# plt.grid(False)

# # Display the correlation coefficient on the plot
# g.ax_joint.text(x.max(), y.min() * 0.75, f'Correlation: {correlation_coef:.2f}', fontsize=12, verticalalignment='bottom', horizontalalignment='right')

# plt.show()



if __name__ == '__main__':
    relevance_pkl_path = "../full_dataset_analysis.relevance.pkl"
    if not os.path.exists(relevance_pkl_path):
        with open("../full_dataset_analysis.pkl", "rb") as f:
            joined_data = pickle.load(f)
        joined_data = compute_avg_relevance()
        with open(relevance_pkl_path, "wb") as f:
            pickle.dump(joined_data, f)
    else:
        with open(relevance_pkl_path, "rb") as f:
            joined_data = pickle.load(f)

    print(joined_data.head())
    print(joined_data['avg_relevance_score'].describe())
    
    plot_avg_relevance_score_distribution(joined_data)