from __future__ import division
import boto3
import nltk.classify.util
from nltk.classify import NaiveBayesClassifier
from nltk.corpus import movie_reviews
from flask import Flask, render_template, request

table_name = 'Movies'
threshold = 0.7

def extract_features(word_list):
    return {word:True for word in word_list}

positive_fileids = movie_reviews.fileids('pos')
negative_fileids = movie_reviews.fileids('neg')
positive_features = [(extract_features(movie_reviews.words(fileids = [f])), 'Positive') for f in positive_fileids]
negative_features = [(extract_features(movie_reviews.words(fileids = [f])), 'Negative') for f in negative_fileids]
threshold_positive = int(threshold * len(positive_features))
threshold_negative = int(threshold * len(negative_features))

features_train = positive_features[:threshold_positive] + negative_features[:threshold_negative]
features_test = positive_features[threshold_positive:] + negative_features[threshold_negative:]
print(len(features_train))

classifier = NaiveBayesClassifier.train(features_train)
print('accuracy of the classifier is: ', nltk.classify.util.accuracy(classifier, features_test))
classifier.show_most_informative_features(10)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('template.html')

@app.route('/my-link/')
def my_link():
    print('I got clicked')
    return 'Click'

def checkTable(dynamodb=None):
    if not dynamodb:
        dynamodb = boto3.client('dynamodb', region_name = 'ap-south-1', aws_access_key_id = 'AKIAQEWLKOZWMEKT2HVP',
         aws_secret_access_key = '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')

    try:
        dynamodb.describe_table(TableName = 'Movies')
    except dynamodb.exceptions.ResourceNotFoundException:
        table = dynamodb.create_table(
            TableName='Movies',
            KeySchema=[
                {
                    'AttributeName': 'title',
                    'KeyType': 'HASH'   # Partition Key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'title',
                    'AttributeType': 'S'
                },

            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10
            }
        )

def upload(title = None, info = None, dynamodb = None, rating = None, comment = None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb', region_name = 'ap-south-1', aws_access_key_id = 'AKIAQEWLKOZWMEKT2HVP',
            aws_secret_access_key = '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')
    item = {
        'title':title,
        'info':info,
        'comments':[[comment, rating]]
            #'artist':{'S':song['artist']},
            #'song':{'S':song['song']},
            #'id':{'S': song['id']},
            #'priceUsdCents':{'S': str(song['priceUsdCents'])},
            #'publisher':{'S': song['publisher']}
    }
    print(item)
    table = dynamodb.Table('Movies')
    response = table.put_item(
        Item=item
    )
    print("UPLOADING ITEM")
    print(response)
    return 'added a new movie ' + title

def query_movie_table(title = None, dynamodb = None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb', region_name = 'ap-south-1', aws_access_key_id = 'AKIAQEWLKOZWMEKT2HVP',
         aws_secret_access_key = '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')
    table = dynamodb.Table(table_name)
    res = table.get_item(
        Key = {
            'title':title
        }
    )
    return res

def add_rating(title = None, rating = None, comment = None, dynamodb = None):
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb', region_name = 'ap-south-1', aws_access_key_id = 'AKIAQEWLKOZWMEKT2HVP',
            aws_secret_access_key = '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')
    table = dynamodb.Table(table_name)
        #UpdateExpression = 
    res = table.update_item(
        Key = {
           'title':title
        },
        UpdateExpression ="SET comments = list_append(comments, :i)",
        ExpressionAttributeValues = {
            ':i': [[comment, rating]]
        }
    )
    return 'added a new comment'

def get_analysis(title = None):
    res = query_movie_table(title)
    print(res)
    sentiments = []
    sent_vals = []
    sum1 = 0
    for comment in res['Item']['comments']:
        print(comment)
        print(comment[0].split())
        prediction = classifier.prob_classify(extract_features(comment[0].split()))
        pred_sentiment = prediction.max()
        print('predicted sentiment: ', pred_sentiment)
        sentiments.append(pred_sentiment)
        temp_sent = round(prediction.prob(pred_sentiment), 2)
        print('probability: ', temp_sent)
        sent_vals.append(temp_sent)
        print('rating is ', comment[1])
        sum1 += int(comment[1])
    #print('ratings are:', ratings)
    #print
    sum = 0
    for i in range(len(sent_vals)):
        if sentiments[i] == 'Positive':
            sum += sent_vals[i]
        else:
            sum += (1 - sent_vals[i])
    print(sum)
    print(len(sent_vals))
    ret_val = 'the over all sentiment is '
    if sum/len(sent_vals) < 0.5:
        ret_val = ret_val + ' negative with a probability of ' + str(1 - sum/len(sent_vals)) + ' and the star rating is ' + str(sum1/len(sent_vals))
    else:
        ret_val = ret_val + ' positive with a probability of' + str(sum/len(sent_vals)) + ' and the star rating is ' + str(sum1/len(sent_vals))
    return ret_val

@app.route('/handle_data', methods = ['POST', 'GET'])
def handle_input():
    if request.method == 'POST':
        if request.form['action'] == 'add movie':
            return render_template("handle_data.html", result = upload(request.form['title'], request.form['info'], None, request.form['rating'], request.form['comment']))
        elif request.form['action'] == 'get rating':
            return render_template("handle_data.html", result = get_analysis(request.form['title']))
        elif request.form['action'] == 'add comment':
            return render_template("handle_data.html", result = add_rating(request.form['title'], request.form['rating'], request.form['comment']))

if __name__ == '__main__':
    checkTable()
    app.run(debug = True, host = "0.0.0.0")
    #print("Table status:", movie_table.table_status)
    #upload()
 #  classifier.
    #print(res['Item']['comments'])

    #for comment in res['Item']['comments']:
    #    prediction = classifier.prob_classify(extract_features(comment.split()))
    #    pred_sentiment = prediction.max()
    #    print(comment)
    #    print('predicted sentiment: ', pred_sentiment)
    #    print('probability: ', round(prediction.prob(pred_sentiment), 2))
    #prediction = classifier.prob_classify(extract_features({c:True for c in 'great riveting outstanding flawless.'.split()}))
    #pred_sentiment = prediction.max()
    #print(pred_sentiment)
    #print('probability: ', round(prediction.prob(pred_sentiment), 2))
    #while True:
    #    option  = input('please choose one of the following: rate, get, show top, stop')
    #    title = input('please give the title of the movie')
    #    if option == 'rate':
    #        rating = input('please choose the number of stars from 1 to 5')
    #        comment = input('please comment your review')
    #        add_rating(title, rating, comment)
    #    if option == 'get':
    #        res = query_movie_table(title)
    #        print(res)
    #    if option == 'stop':
    #        break