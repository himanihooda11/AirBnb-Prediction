from snowflake.snowpark import Session
import sys
import pandas as pd
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
import configparser
import numpy as np
def getProp():
    try:
        global config
        config = configparser.RawConfigParser()
        config.read('config.properties')
        return
    except Exception as err:
        exception_traceback = sys.exc_info()[2]
        err_line = exception_traceback.tb_lineno
        print({"ERROR NAME":"Error in getting configuration properties","ERROR LINE":err_line,"ERROR MESSAGE":str(err)})
        exit()

def makeSnowflakeConnection(connection_name):
    try:
        getProp()
        warehouse = config.get(connection_name, 'warehouse')
        user = config.get(connection_name, 'user')
        password =config.get(connection_name, 'password')
        database = config.get(connection_name, 'database')
        account=config.get(connection_name, 'account')
        schema=config.get(connection_name, 'schema')
        role=config.get(connection_name, 'role')
        conn = dict(
                    user=user,
                    password=password,
                    account=account,
                    warehouse=warehouse,
                    database=database,
                    schema=schema,
                    role=role
                    )
        session = Session.builder.configs(conn).create()
        return session
    except Exception as err:
        exception_traceback = sys.exc_info()[2]
        err_line = exception_traceback.tb_lineno
        print({"ERROR NAME":"Error in makeSnowflakeFunction","ERROR LINE":err_line,"ERROR MESSAGE":str(err)})
        exit()


session=makeSnowflakeConnection('CONNECTION')
print(session)
main_df=pd.DataFrame()
append_data=[]
#df_data=pd.read_csv('combinedListings.csv')
#snowpark_df = session.write_pandas(df, "COMBINED_LISTINGS", auto_create_table=True, table_type="")
q1="""SELECT DISTINCT("neighbourhood_cleansed") FROM REGRESSION.MAIN.COMBINED_LISTINGS"""
neighbourhood_cleansed=pd.DataFrame(session.sql(q1).collect())["neighbourhood_cleansed"].values.tolist()
print(neighbourhood_cleansed)
for val in neighbourhood_cleansed:
    query="""SELECT * FROM REGRESSION.MAIN.COMBINED_LISTINGS where "neighbourhood_cleansed"=$${v}$$;""".format(v=val)
    df=pd.DataFrame(session.sql(query).collect())

    print(df)
    selected_features = [u'id',u'latitude',u'longitude',u'price',u'accommodates',u'host_response_time',
        u'bathrooms', u'bedrooms', u'beds', u'minimum_nights', u'maximum_nights',
        u'availability_365',
        u'number_of_reviews', u'review_scores_rating',u'review_scores_cleanliness', u'review_scores_checkin',
        u'review_scores_communication', u'review_scores_location',
        u'review_scores_value',u'amenities', 'room_type', 'property_type']
    df = df.loc[:, selected_features]
    # print(df)
    # df = df.apply(lambda x:x.fillna(x.value_counts().index[0]))
    print(df["price"])
    df['price'] = df['price'].str.replace("\$|,", "").astype(float)
    df['availability'] = df['availability_365'] / 365

    import re
    # AMENITIES
    amenities = list(df['amenities'])
    total = ','.join(amenities)
    total = total.replace("{", "").replace("}","").replace("\"", "").split(",")
    amenity_items = list(set(total))
    amenity_items = list(filter(None, amenity_items))
    for item in amenity_items:
        if re.match(r'translation',item):
            amenity_items.remove(item)


    amenities = list(df['amenities'])
    new_table = pd.DataFrame(index = df.reset_index().values[:,0], columns = amenity_items).fillna(0)

    for i in range(len(amenities)):
        for item in amenity_items:
            if item in amenities[i]:
                new_table.at[i, item]= 1

    sum_table = np.array(new_table.sum())
    ind = (-sum_table).argsort()[:60]
    common_amenities = list(new_table.sum().iloc[ind].index)
    df = df.drop(['amenities'], axis = 1)
    df = pd.concat([df, new_table[common_amenities]], axis = 1)
    print(df)

    columns = ['room_type', 'property_type']
    for column in columns:  
        unique_values = list(df[column].unique())
        column_list = list(df[column])
        new_table = pd.DataFrame(index = df.reset_index().values[:,0], columns = unique_values).fillna(0)
        
        for i in range(len( column_list )):
            for item in unique_values:
                if item in column_list[i]:
                    new_table.at[i, item]= 1  
        df = pd.concat( [df, new_table], axis = 1)
        df = df.drop([column], axis = 1)

    df=df.drop(['host_response_time', 'bathrooms'], axis = 1)
    print(df)
    print(list(df.select_dtypes(['object']).columns))
    from sklearn.cluster import KMeans
    from sklearn import preprocessing
    df = df.fillna(0)
    df2=df.drop(['id','price','latitude','longitude'], axis = 1)
    X = np.array(df2)
    X_scaled = preprocessing.scale(X)
    y_pred = KMeans(n_clusters=3, random_state=170).fit_predict(X_scaled)
    df["CLUSTER"]=y_pred
    print(df["CLUSTER"])
    df3=df[["id","latitude","longitude","CLUSTER"]]
    #snowpark_df = session.write_pandas(df3, val, auto_create_table=True, table_type="transient")
