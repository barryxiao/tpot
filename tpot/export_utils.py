# -*- coding: utf-8 -*-

"""
Copyright 2015 Randal S. Olson

This file is part of the TPOT library.

The TPOT library is free software: you can redistribute it and/or
modify it under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your option)
any later version.

The TPOT library is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with
the Twitter Bot library. If not, see http://www.gnu.org/licenses/.
"""

# Utility functions that convert the current optimized pipeline into its corresponding Python code
# For usage, see export() function in tpot.py

import deap


def replace_mathematical_operators(exported_pipeline):
    """Replace all of the mathematical operators with their results for use in export(self, output_file_name)

    Parameters
    ----------
    exported_pipeline:
       The current optimized pipeline

    Returns
    -------
    exported_pipeline:
       The current optimized pipeline after replacing the mathematical operators

    """

    while True:
        for i in range(len(exported_pipeline) - 1, -1, -1):
            node = exported_pipeline[i]
            if type(node) is deap.gp.Primitive and node.name in ['add', 'sub', 'mul', '_div']:
                val1 = int(exported_pipeline[i + 1].name)
                val2 = int(exported_pipeline[i + 2].name)
                if node.name == 'add':
                    new_val = val1 + val2
                elif node.name == 'sub':
                    new_val = val1 - val2
                elif node.name == 'mul':
                    new_val = val1 * val2
                else:
                    if val2 == 0:
                        new_val = 0
                    else:
                        new_val = float(val1) / float(val2)

                new_val = deap.gp.Terminal(symbolic=new_val, terminal=new_val, ret=new_val)
                exported_pipeline = exported_pipeline[:i] + [new_val] + exported_pipeline[i + 3:]
                break
        else:
            break

    return exported_pipeline

def unroll_nested_fuctions_calls(exported_pipeline):
    """Unroll the nested function calls into serial code for use in export(self, output_file_name)

    Parameters
    ----------
    exported_pipeline:
       The current optimized pipeline

    Returns
    -------
    exported_pipeline:
       The current optimized pipeline after unrolling the nested function calls
    pipeline_list:
       List of operators in the current optimized pipeline

    """

    pipeline_list = []
    result_num = 1
    while True:
        for node_index in range(len(exported_pipeline) - 1, -1, -1):
            node = exported_pipeline[node_index]
            if type(node) is not deap.gp.Primitive:
                continue

            node_params = exported_pipeline[node_index + 1:node_index + node.arity + 1]

            new_val = 'result{}'.format(result_num)
            operator_list = [new_val, node.name]
            operator_list.extend([x.name for x in node_params])
            pipeline_list.append(operator_list)
            result_num += 1
            new_val = deap.gp.Terminal(symbolic=new_val, terminal=new_val, ret=new_val)
            exported_pipeline = exported_pipeline[:node_index] + [new_val] + exported_pipeline[node_index + node.arity + 1:]
            break
        else:
            break
    return exported_pipeline, pipeline_list

def replace_function_calls(pipeline_list):
    """Replace the function calls with their corresponding Python code for use in export(self, output_file_name)

    Parameters
    ----------
    pipeline_list:
       List of operators in the current optimized pipeline

    Returns
    -------
    operator_text:
       The python code corresponding to the function calls in the current optimized pipeline

    """

    for operator in pipeline_list:
        operator_num = int(operator[0].strip('result'))
        result_name = operator[0]
        operator_name = operator[1]
        operator_text = ''

        # Make copies of the data set for each reference to ARG0
        if operator[2] == 'ARG0':
            operator[2] = 'result{}'.format(operator_num)
            operator_text += '\n{} = tpot_data.copy()\n'.format(operator[2])

        if len(operator) > 3 and operator[3] == 'ARG0':
            operator[3] = 'result{}'.format(operator_num)
            operator_text += '\n{} = tpot_data.copy()\n'.format(operator[3])

        # Replace the TPOT functions with their corresponding Python code
        if operator_name == 'decision_tree':
            max_features = int(operator[3])
            max_depth = int(operator[4])

            if max_features < 1:
                max_features = '\'auto\''
            elif max_features == 1:
                max_features = None
            else:
                max_features = 'min({}, len({}.columns) - 1)'.format(max_features, operator[2])

            if max_depth < 1:
                max_depth = None

            operator_text += '\n# Perform classification with a decision tree classifier'
            operator_text += '\ndtc{} = DecisionTreeClassifier(max_features={}, max_depth={})\n'.format(operator_num, max_features, max_depth)
            operator_text += '''dtc{0}.fit({1}.loc[training_indices].drop('class', axis=1).values, {1}.loc[training_indices, 'class'].values)\n'''.format(operator_num, operator[2])
            if result_name != operator[2]:
                operator_text += '{} = {}\n'.format(result_name, operator[2])
            operator_text += '''{0}['dtc{1}-classification'] = dtc{1}.predict({0}.drop('class', axis=1).values)\n'''.format(result_name, operator_num)

        elif operator_name == 'random_forest':
            num_trees = int(operator[3])
            max_features = int(operator[4])

            if num_trees < 1:
                num_trees = 1
            elif num_trees > 500:
                num_trees = 500

            if max_features < 1:
                max_features = '\'auto\''
            elif max_features == 1:
                max_features = 'None'
            else:
                max_features = 'min({}, len({}.columns) - 1)'.format(max_features, operator[2])

            operator_text += '\n# Perform classification with a random forest classifier'
            operator_text += '\nrfc{} = RandomForestClassifier(n_estimators={}, max_features={})\n'.format(operator_num, num_trees, max_features)
            operator_text += '''rfc{0}.fit({1}.loc[training_indices].drop('class', axis=1).values, {1}.loc[training_indices, 'class'].values)\n'''.format(operator_num, operator[2])
            if result_name != operator[2]:
                operator_text += '{} = {}\n'.format(result_name, operator[2])
            operator_text += '''{0}['rfc{1}-classification'] = rfc{1}.predict({0}.drop('class', axis=1).values)\n'''.format(result_name, operator_num)

        elif operator_name == 'logistic_regression':
            C = float(operator[3])
            if C <= 0.:
                C = 0.0001

            operator_text += '\n# Perform classification with a logistic regression classifier'
            operator_text += '\nlrc{} = LogisticRegression(C={})\n'.format(operator_num, C)
            operator_text += '''lrc{0}.fit({1}.loc[training_indices].drop('class', axis=1).values, {1}.loc[training_indices, 'class'].values)\n'''.format(operator_num, operator[2])
            if result_name != operator[2]:
                operator_text += '{} = {}\n'.format(result_name, operator[2])
            operator_text += '''{0}['lrc{1}-classification'] = lrc{1}.predict({0}.drop('class', axis=1).values)\n'''.format(result_name, operator_num)

        elif operator_name == 'svc':
            C = float(operator[3])
            if C <= 0.:
                C = 0.0001

            operator_text += '\n# Perform classification with a C-support vector classifier'
            operator_text += '\nsvc{} = SVC(C={})\n'.format(operator_num, C)
            operator_text += '''svc{0}.fit({1}.loc[training_indices].drop('class', axis=1).values, {1}.loc[training_indices, 'class'].values)\n'''.format(operator_num, operator[2])
            if result_name != operator[2]:
                operator_text += '{} = {}\n'.format(result_name, operator[2])
            operator_text += '''{0}['svc{1}-classification'] = svc{1}.predict({0}.drop('class', axis=1).values)\n'''.format(result_name, operator_num)

        elif operator_name == 'knnc':
            n_neighbors = int(operator[3])
            if n_neighbors < 2:
                n_neighbors = 2
            else:
                n_neighbors = 'min({}, len(training_indices))'.format(n_neighbors)

            operator_text += '\n# Perform classification with a k-nearest neighbor classifier'
            operator_text += '\nknnc{} = KNeighborsClassifier(n_neighbors={})\n'.format(operator_num, n_neighbors)
            operator_text += '''knnc{0}.fit({1}.loc[training_indices].drop('class', axis=1).values, {1}.loc[training_indices, 'class'].values)\n'''.format(operator_num, operator[2])
            if result_name != operator[2]:
                operator_text += '{} = {}\n'.format(result_name, operator[2])
            operator_text += '''{0}['knnc{1}-classification'] = knnc{1}.predict({0}.drop('class', axis=1).values)\n'''.format(result_name, operator_num)

        elif operator_name == 'gradient_boosting':
            learning_rate = float(operator[3])
            n_estimators = int(operator[4])
            max_depth = int(operator[5])

            if learning_rate <= 0.:
                learning_rate = 0.0001

            if n_estimators < 1:
                n_estimators = 1
            elif n_estimators > 500:
                n_estimators = 500

            if max_depth < 1:
                max_depth = None

            operator_text += '\n# Perform classification with a gradient boosting classifier'
            operator_text += '\ngbc{} = GradientBoostingClassifier(learning_rate={}, n_estimators={}, max_depth={})\n'.format(operator_num, learning_rate, n_estimators, max_depth)
            operator_text += '''gbc{0}.fit({1}.loc[training_indices].drop('class', axis=1).values, {1}.loc[training_indices, 'class'].values)\n'''.format(operator_num, operator[2])
            if result_name != operator[2]:
                operator_text += '{} = {}\n'.format(result_name, operator[2])
            operator_text += '''{0}['gbc{1}-classification'] = gbc{1}.predict({0}.drop('class', axis=1).values)\n'''.format(result_name, operator_num)

        elif operator_name == '_combine_dfs':
            operator_text += '\n# Combine two DataFrames'
            operator_text += '\n{2} = {0}.join({1}[[column for column in {1}.columns.values if column not in {0}.columns.values]])\n'.format(operator[2], operator[3], result_name)

        elif operator_name == '_variance_threshold':
            operator_text += '''
# Use Scikit-learn's VarianceThreshold for feature selection
training_features = {0}.loc[training_indices].drop('class', axis=1)

selector = VarianceThreshold(threshold={1})
try:
selector.fit(training_features.values)
except ValueError:
# None of the features meet the variance threshold
{2} = {0}[['class']]

mask = selector.get_support(True)
mask_cols = list(training_features.iloc[:, mask].columns) + ['class']
{2} = {0}[mask_cols]
'''.format(operator[2], operator[3], result_name)

        elif operator_name == '_select_kbest':
            k = int(operator[3])

            if k < 1:
                k = 1

            k = 'min({}, len(training_features.columns))'.format(k)

            operator_text += '''
# Use Scikit-learn's SelectKBest for feature selection
training_features = {0}.loc[training_indices].drop('class', axis=1)
training_class_vals = {0}.loc[training_indices, 'class'].values

if len(training_features.columns.values) == 0:
{2} = {0}.copy()
else:
selector = SelectKBest(f_classif, k={1})
selector.fit(training_features.values, training_class_vals)
mask = selector.get_support(True)
mask_cols = list(training_features.iloc[:, mask].columns) + ['class']
{2} = {0}[mask_cols]
'''.format(operator[2], k, result_name)

        elif operator_name == '_select_percentile':
            percentile = int(operator[3])

            if percentile < 0:
                percentile = 0
            elif percentile > 100:
                percentile = 100

            operator_text += '''
# Use Scikit-learn's SelectPercentile for feature selection
training_features = {0}.loc[training_indices].drop('class', axis=1)
training_class_vals = {0}.loc[training_indices, 'class'].values

if len(training_features.columns.values) == 0:
{2} = {0}.copy()
else:
selector = SelectPercentile(f_classif, percentile={1})
selector.fit(training_features.values, training_class_vals)
mask = selector.get_support(True)
mask_cols = list(training_features.iloc[:, mask].columns) + ['class']
{2} = {0}[mask_cols]
'''.format(operator[2], percentile, result_name)

        elif operator_name == '_rfe':
            n_features_to_select = int(operator[3])
            step = float(operator[4])

            if n_features_to_select < 1:
                n_features_to_select = 1
            n_features_to_select = 'min({}, len(training_features.columns))'.format(n_features_to_select)

            if step < 0.1:
                step = 0.1
            elif step >= 1.:
                step = 0.99

            operator_text += '''
# Use Scikit-learn's Recursive Feature Elimination (RFE) for feature selection
training_features = {0}.loc[training_indices].drop('class', axis=1)
training_class_vals = {0}.loc[training_indices, 'class'].values

if len(training_features.columns.values) == 0:
{3} = {0}.copy()
else:
selector = RFE(SVC(kernel='linear'), n_features_to_select={1}, step={2})
selector.fit(training_features.values, training_class_vals)
mask = selector.get_support(True)
mask_cols = list(training_features.iloc[:, mask].columns) + ['class']
{3} = {0}[mask_cols]
'''.format(operator[2], n_features_to_select, step, result_name)

        elif operator_name == '_standard_scaler':
            operator_text += '''
# Use Scikit-learn's StandardScaler to scale the features
training_features = {0}.loc[training_indices].drop('class', axis=1)
{1} = {0}.copy()

if len(training_features.columns.values) > 0:
scaler = StandardScaler()
scaler.fit(training_features.values.astype(np.float64))
scaled_features = scaler.transform({1}.drop('class', axis=1).values.astype(np.float64))

for col_num, column in enumerate({1}.drop('class', axis=1).columns.values):
    {1}.loc[:, column] = scaled_features[:, col_num]
'''.format(operator[2], result_name)

        elif operator_name == '_robust_scaler':
            operator_text += '''
# Use Scikit-learn's RobustScaler to scale the features
training_features = {0}.loc[training_indices].drop('class', axis=1)
{1} = {0}.copy()

if len(training_features.columns.values) > 0:
scaler = RobustScaler()
scaler.fit(training_features.values.astype(np.float64))
scaled_features = scaler.transform({1}.drop('class', axis=1).values.astype(np.float64))

for col_num, column in enumerate({1}.drop('class', axis=1).columns.values):
    {1}.loc[:, column] = scaled_features[:, col_num]
'''.format(operator[2], result_name)

        elif operator_name == '_polynomial_features':
            operator_text += '''
# Use Scikit-learn's PolynomialFeatures to construct new features from the existing feature set
training_features = {0}.loc[training_indices].drop('class', axis=1)

if len(training_features.columns.values) > 0 and len(training_features.columns.values) <= 700:
# The feature constructor must be fit on only the training data
poly = PolynomialFeatures(degree=2, include_bias=False)
poly.fit(training_features.values.astype(np.float64))
constructed_features = poly.transform({0}.drop('class', axis=1).values.astype(np.float64))

{0}_classes = {0}['class'].values
{1} = pd.DataFrame(data=constructed_features)
{1}['class'] = {0}_classes
else:
{1} = {0}.copy()
'''.format(operator[2], result_name)

        elif operator_name == '_pca':
            n_components = int(operator[3])
            if n_components < 1:
                n_components = 1
            n_components = 'min({}, len(training_features.columns.values))'.format(n_components)

            operator_text += '''
# Use Scikit-learn's PCA to transform the feature set
training_features = {0}.loc[training_indices].drop('class', axis=1)

if len(training_features.columns.values) > 0:
# PCA must be fit on only the training data
pca = PCA(n_components={1})
pca.fit(training_features.values.astype(np.float64))
transformed_features = pca.transform({0}.drop('class', axis=1).values.astype(np.float64))

{0}_classes = {0}['class'].values
{2} = pd.DataFrame(data=transformed_features)
{2}['class'] = {0}_classes
else:
{2} = {0}.copy()
'''.format(operator[2], n_components, result_name)

    return operator_text
