import streamlit as st
import pandas as pd
import numpy as np
import folium as fl
import geopandas as gpd
from folium.plugins import BeautifyIcon
import zipfile
from PIL import Image


BaseColor=['#80BBAD', '#435254', '#17E88F', '#DBD99A', '#D2785A', '#885073', '#A388BF', '#1F3765', '#3E7CA6', '#CAD1D3']
PU_Start='<div style="font-size: 10pt; color : #435254; font-weight: bold;"><span style="white-space: nowrap;">'
PU_End='</span></div>'

df_Stacking_dtype={
    'GRID_BID':str,
    'Property':str,
    'Address':str,
    'sfa':float,
    'gfa':float,
    'Bldg_Usage':str,
    'POINT_Y':float,
    'POINT_X':float,
    'User_Usage':str,
    'CorpNum':str,
    'Comp_Name':str,
    'Lease_Area':float,
    'CNT_Type':str,
    'CNT_Start':str,
    'CNT_End':str,
    'kilo':str
}

df_Sansan_dtype={
    'CBRE_Div':str,
    'CBRE_Member':str,
    'Comp_Name':str,
    'Comp_Eng':str, 
    'Div':str,
    'Title':str,
    'PostCode':int,
    'Address':str,
    'TEL':str,
    'FAX':str,
    'Date':str,
    'CorpNum':str
}

df_MsbGeo_dtype={
    'Comp_Name':str,
    'Branch_Name':str,
    'Branch_1':str,
    'Branch_2':str,
    'Branch_3':str,
    'Address':str,
    'Tel':str,
    'Address_Type':str,
    'PostCode':int,
    'CorpNum':str,
    'Capital':float,
    'Revenue':float,
    'Num_Branch':float,
    'Num_Employee':float,
    'Num_Factory':float,
    'Num_Shop':float,
    'Ind_Main1':str,
    'Ind_Main2':str,
    'Ind_Sub1':str,
    'Ind_Sub2':str,
    'POINT_X':float,
    'POINT_Y':float
}

st.set_page_config(layout="wide")
st.title('Tenant Radar APP')

with st.sidebar:
    zip_Capsule=st.file_uploader(label='Upload Capsule.zip',type='zip')
    if zip_Capsule is not None:
        with zipfile.ZipFile(zip_Capsule,'r') as z:
            with z.open('02_PropGeo.zip') as f:
                gdf_PropGeo=gpd.read_file(f,encoding='utf-8')
            with z.open('03_Ring.zip') as f:
                gdf_Ring=gpd.read_file(f,encoding='utf-8')
            with z.open('05_PostCode.csv') as f:
                df_PostCode=pd.read_csv(f,encoding='utf-8')
            with z.open('06_MsbGeo.csv') as f:
                df_MsbGeo=pd.read_csv(f,encoding='utf-8',dtype=df_MsbGeo_dtype)
            with z.open('07_Stacking.csv') as f:
                df_Stacking=pd.read_csv(f,encoding='utf-8',dtype=df_Stacking_dtype)
            with z.open('08_Sansan.csv') as f:
                df_Sansan=pd.read_csv(f,encoding='utf-8',dtype=df_Sansan_dtype)
            with z.open('09_Sansan_CBRE.csv') as f:
                df_CBREDiv=pd.read_csv(f,encoding='utf-8')

if zip_Capsule is None:
    image=Image.open('ACube.PNG')
    st.image(image,width=400)
    

if zip_Capsule is not None:       
    with st.sidebar:
        kilo=st.select_slider('Ring Kilo :',gdf_Ring.kilo.values,gdf_Ring.kilo.values[2])
        PostCodeList=df_PostCode[df_PostCode.kilo==kilo].PostCode.values
        df_MsbGeo=df_MsbGeo[df_MsbGeo.PostCode.isin(PostCodeList)].reset_index(drop=True)
        df_Stacking=df_Stacking[df_Stacking.kilo==kilo].reset_index(drop=True)
        df_Sansan=df_Sansan[df_Sansan.PostCode.isin(PostCodeList)].reset_index(drop=True)
        SMap=fl.Map(
            location=[gdf_PropGeo.loc[0,'POINT_Y'],gdf_PropGeo.loc[0,'POINT_X']],
            tiles='cartodbpositron',
            zoom_start=8
        )
        Group=fl.FeatureGroup(name=gdf_PropGeo.loc[0,'Label'],show=True).add_to(SMap)
        PU='<br>'.join([gdf_PropGeo.loc[0,'Label'],gdf_PropGeo.loc[0,'Property'],gdf_PropGeo.loc[0,'Address']])
        Group.add_child(
            fl.Marker(
                location=[gdf_PropGeo.loc[0,'POINT_Y'],gdf_PropGeo.loc[0,'POINT_X']],
                popup=PU_Start+PU+PU_End,
                icon=BeautifyIcon(icon='star',border_width=2,border_color=BaseColor[0],text_color=BaseColor[0],spin=True)   
            )
        )
        st.components.v1.html(fl.Figure().add_child(SMap).render(),height=300)

    col1,col2,col3,col4,col5,col6=st.columns(6)


    Mcol1,Mcol2=st.columns(2)

    with Mcol2:
        tab1,tab2,tab3,tab4=st.tabs(['Summary','Stacking','Sansan','Musubu'])
        with tab2:
            Lease_Area_Min=st.number_input(
                '賃貸面積 From',
                min_value=df_Stacking.Lease_Area.min(),
                max_value=df_Stacking.Lease_Area.max(),
                value=df_Stacking.Lease_Area.min()
            )
            Lease_Area_Max=st.number_input(
                '賃貸面積 To',
                min_value=df_Stacking.Lease_Area.min(),
                max_value=df_Stacking.Lease_Area.max(),
                value=df_Stacking.Lease_Area.max()
            )
            GRID_BID_List=st.multiselect(
                label='GRID番号',
                options=df_Stacking.GRID_BID.value_counts().index,
                default=[]
            )
            if len(GRID_BID_List)!=0:
                df_Stacking=df_Stacking[
                    (df_Stacking.GRID_BID.isin(GRID_BID_List))&
                    (df_Stacking.Lease_Area>=Lease_Area_Min)&
                    (df_Stacking.Lease_Area<=Lease_Area_Max)
                ].reset_index(drop=True)
            else:
                df_Stacking=df_Stacking[
                    (df_Stacking.Lease_Area>=Lease_Area_Min)&
                    (df_Stacking.Lease_Area<=Lease_Area_Max)
                ].reset_index(drop=True)
            st.dataframe(
                df_Stacking[[
                    'CorpNum','Comp_Name','GRID_BID','Property','Address','Lease_Area','CNT_Type','CNT_Start','CNT_End'
                ]].sort_values('Lease_Area',ascending=False),
                height=420,use_container_width=True
            )
        with tab3:
            CBRE_Div_List=st.multiselect(
                label='CBRE Division',
                options=df_CBREDiv.CBRE_Div.value_counts().index,
                default=[]
            )
            if len(CBRE_Div_List)!=0:
                Sansan_CBRE_Div_List=df_CBREDiv[df_CBREDiv.CBRE_Div.isin(CBRE_Div_List)].Sansan_Div.value_counts().index
                df_Sansan=df_Sansan[df_Sansan.CBRE_Div.isin(Sansan_CBRE_Div_List)].reset_index(drop=True)
            Sansan_PostCode_List=st.multiselect(
                label='Sansan 郵便番号',
                options=PostCodeList,
                default=[]
            )
            if len(Sansan_PostCode_List)!=0:
                df_Sansan=df_Sansan[df_Sansan.PostCode.isin(Sansan_PostCode_List)].reset_index(drop=True)
            st.dataframe(
                df_Sansan[[
                    'CorpNum','Comp_Name','Div','Title','Address','CBRE_Div','CBRE_Member','PostCode'
                ]].sort_values('Comp_Name'),
                height=420,use_container_width=True
            )

        with tab4:
            Ind_Main1_List=st.multiselect(
                label='メイン大業界',
                options=df_MsbGeo.Ind_Main1.value_counts().index,
                default=[]
            )
            if len(Ind_Main1_List)!=0:
                df_MsbGeo=df_MsbGeo[df_MsbGeo.Ind_Main1.isin(Ind_Main1_List)].reset_index(drop=True)
            Msb_PostCode_List=st.multiselect(
                label='Musubu 郵便番号',
                options=PostCodeList,
                default=[]
            )
            if len(Msb_PostCode_List)!=0:
                df_MsbGeo=df_MsbGeo[df_MsbGeo.PostCode.isin(Msb_PostCode_List)].reset_index(drop=True)
            if 'Tel' in df_MsbGeo.columns:
                st.dataframe(
                    df_MsbGeo[[
                        'CorpNum','Comp_Name','Branch_Name','Address','Tel','Branch_1','Ind_Main1','PostCode'
                    ]].sort_values('Comp_Name'),
                    height=420,use_container_width=True
                )
            else:
                st.dataframe(
                    df_MsbGeo[[
                        'CorpNum','Comp_Name','Branch_Name','Address','Branch_1','Ind_Main1','PostCode'
                    ]].sort_values('Comp_Name'),
                    height=420,use_container_width=True
                )
        with tab1:
            SumSort=st.radio(
                label='ソート',
                options=['Stacking','Sansan','Musubu']
            )
            df_Sum=pd.concat([
                df_MsbGeo.drop_duplicates(subset=['CorpNum','Comp_Name'])[['CorpNum','Comp_Name']],
                df_Sansan.drop_duplicates(subset=['CorpNum','Comp_Name'])[['CorpNum','Comp_Name']],
                df_Stacking.drop_duplicates(subset=['CorpNum','Comp_Name'])[['CorpNum','Comp_Name']]
            ]).drop_duplicates(subset='CorpNum').set_index('CorpNum')\
            .assign(Stacking=df_Stacking.CorpNum.value_counts())\
            .assign(Sansan=df_Sansan.CorpNum.value_counts())\
            .assign(Musubu=df_MsbGeo.CorpNum.value_counts())\
            .fillna(0)
            df_Sum.Stacking=df_Sum.Stacking.astype(int)
            df_Sum.Sansan=df_Sum.Sansan.astype(int)
            df_Sum.Musubu=df_Sum.Musubu.astype(int)
            st.dataframe(
                df_Sum.sort_values(SumSort,ascending=False).style.highlight_min(color='black'),
                height=420,use_container_width=True
            )

    ################################################################################################
    with col1:
        st.metric('Musubu 事業所数',len(df_MsbGeo))
    with col2:
        st.metric('Stacking テナント数',len(df_Stacking))
    with col3:
        st.metric('Sansan 名刺数',len(df_Sansan))
    ################################################################################################
    Map=fl.Map(
        location=[gdf_PropGeo.loc[0,'POINT_Y'],gdf_PropGeo.loc[0,'POINT_X']],
        tiles='cartodbpositron',
        zoom_start=13
    )
    Group=fl.FeatureGroup(name=gdf_PropGeo.loc[0,'Label'],show=True).add_to(Map)
    PU='<br>'.join([gdf_PropGeo.loc[0,'Label'],gdf_PropGeo.loc[0,'Property'],gdf_PropGeo.loc[0,'Address']])
    Group.add_child(
        fl.Marker(
            location=[gdf_PropGeo.loc[0,'POINT_Y'],gdf_PropGeo.loc[0,'POINT_X']],
            popup=PU_Start+PU+PU_End,
            icon=BeautifyIcon(icon='star',border_width=2,border_color=BaseColor[0],text_color=BaseColor[0],spin=True)   
        )
    )
    Group=fl.FeatureGroup(name=f'{kilo}Ring',show=True).add_to(Map)
    Group.add_child(
        fl.GeoJson(
            data=gdf_Ring[gdf_Ring.kilo==kilo],
            # popup=fl.GeoJsonPopup(fields=(['kilo']),labels=False),
            style_function=lambda x:{'fillColor':BaseColor[0],'color':BaseColor[0],'weight':2,'fillOpacity':0.1}
        )
    )
    Group=fl.FeatureGroup(name=f'{kilo}Ring 郵便番号',show=True).add_to(Map)
    for PostCode in PostCodeList:
        POINT_X=df_PostCode[df_PostCode.PostCode==PostCode].POINT_X.values[0]
        POINT_Y=df_PostCode[df_PostCode.PostCode==PostCode].POINT_Y.values[0]
        PostStr='〒'+str(PostCode)
        Msb_Num=len(df_MsbGeo[df_MsbGeo.PostCode==PostCode])
        San_Num=len(df_Sansan[df_Sansan.PostCode==PostCode])
        PU='<br>'.join([PostStr,f'Musubu : {Msb_Num}社',f'Sansan : {San_Num}枚'])
        if Msb_Num+San_Num!=0:
            Group.add_child(fl.CircleMarker(
                location=[POINT_Y,POINT_X],
                radius=2,
                weight=6,
                color='#fd8d3c',
                popup=PU_Start+PU+PU_End
            ))
    if len(GRID_BID_List)==0:
        GRID_BID_List=df_Stacking.GRID_BID.value_counts().index
    
    Group=fl.FeatureGroup(name=f'{kilo}Ring Stacking',show=True).add_to(Map)
    for GRID_BID in GRID_BID_List:
        if len(df_Stacking[df_Stacking.GRID_BID==GRID_BID])!=0:
            POINT_X=df_Stacking[df_Stacking.GRID_BID==GRID_BID].POINT_X.values[0]
            POINT_Y=df_Stacking[df_Stacking.GRID_BID==GRID_BID].POINT_Y.values[0]
            Property=df_Stacking[df_Stacking.GRID_BID==GRID_BID].Property.values[0]
            Comp_Num=len(df_Stacking[df_Stacking.GRID_BID==GRID_BID])
            PU='<br>'.join([str(GRID_BID),Property,f'{Comp_Num}社'])
            Group.add_child(fl.CircleMarker(
                location=[POINT_Y,POINT_X],
                radius=2,
                weight=6,
                color='#74c476',
                popup=PU_Start+PU+PU_End
            ))      
    fl.LayerControl().add_to(Map)

    with Mcol1:
        st.components.v1.html(fl.Figure().add_child(Map).render(),height=650)
    with st.sidebar:
        st.subheader(f'Stacking  : {Lease_Area_Min} 坪 ~ {Lease_Area_Max} 坪')
        if len(CBRE_Div_List)==0:
            st.subheader('Sansan : All CBRE Divisions')
        else:
            st.subheader('Sansan : '+' , '.join(CBRE_Div_List))
        if len(Ind_Main1_List)==0:
            st.subheader('Musubu : 全業界')
        else:
            st.subheader('Musubu : '+' , '.join(Ind_Main1_List))
        st.download_button('🗺️ Map Download', fl.Figure().add_child(Map).render(),file_name='Map.html')
        st.download_button('📋 Download Summary csv', df_Sum.to_csv(index=False).encode('utf-8-sig'),file_name='Summary.csv')
        st.download_button('📋 Download Musubu csv', df_MsbGeo.to_csv(index=False).encode('utf-8-sig'),file_name='Musubu.csv')
        st.download_button('📋 Download Stacking csv', df_Stacking.to_csv(index=False).encode('utf-8-sig'),file_name='Stacking.csv')
        st.download_button('📋 Download Sansan csv', df_Sansan.to_csv(index=False).encode('utf-8-sig'),file_name='Sansan.csv')


