"""
Tenant Radar APP
================
リファクタ版。主な変更点:

1. CARTO basemap の API キーを st.secrets / 環境変数から取得（ソース非埋め込み）
2. Capsule.zip のパースを @st.cache_data 化
3. マーカー描画ループを groupby / value_counts に置換
4. 地図の render() を 1 回だけに
5. フィルタの破壊的上書きを廃止（元データを保持）
6. Summary CSV の CorpNum 欠落を修正
7. 郵便番号の先頭ゼロを保持（7桁 zfill 文字列に正規化）
8. zoomlevel / 画像パス / 空データのガード追加

--------------------------------------------------------------------------
CARTO API キーの設定
--------------------------------------------------------------------------
ローカル: リポジトリ直下に .streamlit/secrets.toml を作成（.gitignore に追加すること）

    [carto]
    api_key = "xxxxxxxxxxxx"

Streamlit Community Cloud: App の Settings > Secrets に上記 TOML をそのまま貼り付け

その他のホスト: 環境変数 CARTO_API_KEY を設定

※ キーはタイル URL としてブラウザに送出されるため、エンドユーザーからは秘匿されません。
   st.secrets の目的は「Git 履歴に残さないこと」です。
--------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import folium as fl
import geopandas as gpd
import pandas as pd
import streamlit as st
from folium.plugins import BeautifyIcon
from PIL import Image

APP_DIR = Path(__file__).resolve().parent

# ==========================================================================
# 定数
# ==========================================================================

BASE_COLOR = [
    "#80BBAD", "#435254", "#17E88F", "#DBD99A", "#D2785A",
    "#885073", "#A388BF", "#1F3765", "#3E7CA6", "#CAD1D3",
]

PU_START = (
    '<div style="font-size: 10pt; color : #435254; font-weight: bold;">'
    '<span style="white-space: nowrap;">'
)
PU_END = "</span></div>"

POSTCODE_LEN = 7

DTYPE_STACKING = {
    "GRID_BID": str, "Property": str, "Address": str,
    "sfa": float, "gfa": float, "Bldg_Usage": str,
    "POINT_Y": float, "POINT_X": float, "User_Usage": str,
    "CorpNum": str, "Comp_Name": str, "Lease_Area": float,
    "CNT_Type": str, "CNT_Start": str, "CNT_End": str, "kilo": str,
}

# PostCode は int ではなく str（先頭ゼロを保持するため）
DTYPE_SANSAN = {
    "CBRE_Div": str, "CBRE_Member": str, "Comp_Name": str, "Comp_Eng": str,
    "Div": str, "Title": str, "PostCode": str, "Address": str,
    "TEL": str, "FAX": str, "Date": str, "CorpNum": str,
}

DTYPE_MSBGEO = {
    "Comp_Name": str, "Branch_Name": str,
    "Branch_1": str, "Branch_2": str, "Branch_3": str,
    "Address": str, "Tel": str, "Address_Type": str, "PostCode": str,
    "CorpNum": str, "Capital": float, "Revenue": float,
    "Num_Branch": float, "Num_Employee": float,
    "Num_Factory": float, "Num_Shop": float,
    "Ind_Main1": str, "Ind_Main2": str, "Ind_Sub1": str, "Ind_Sub2": str,
    "POINT_X": float, "POINT_Y": float,
}

# ==========================================================================
# CARTO basemap
# ==========================================================================

CARTO_STYLE = "light_all"  # Positron with labels
CARTO_ATTR = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors '
    '&copy; <a href="https://carto.com/attributions">CARTO</a>'
)


def get_carto_key() -> str:
    """CARTO basemap の API キーを secrets → 環境変数の順で取得する。"""
    try:
        key = st.secrets["carto"]["api_key"]
    except Exception:
        # secrets.toml が存在しないローカル実行などでは例外になるため握りつぶす
        key = ""
    return key or os.environ.get("CARTO_API_KEY", "")


def carto_tile_layer() -> fl.TileLayer:
    """キー付き CARTO ラスタタイルの TileLayer を返す。"""
    url = f"https://basemaps.cartocdn.com/rastertiles/{CARTO_STYLE}/{{z}}/{{x}}/{{y}}.png"
    key = get_carto_key()
    if key:
        url += f"?key={key}"
    return fl.TileLayer(
        tiles=url,
        attr=CARTO_ATTR,   # CARTO / OSM のクレジットは規約上必須
        name="CARTO Positron",
        max_zoom=20,
        control=False,
    )


def new_map(lat: float, lon: float, zoom: int) -> fl.Map:
    m = fl.Map(location=[lat, lon], tiles=None, zoom_start=zoom)
    carto_tile_layer().add_to(m)
    return m


# ==========================================================================
# データ読み込み
# ==========================================================================


def _norm_postcode(s: pd.Series) -> pd.Series:
    """郵便番号を 7 桁ゼロ埋め文字列に正規化する（先頭ゼロ落ち対策）。"""
    return (
        s.astype(str)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(POSTCODE_LEN)
    )


@st.cache_data(show_spinner="Capsule を読み込んでいます…")
def load_capsule(raw: bytes) -> dict:
    """Capsule.zip をパースして DataFrame 群を返す。bytes を引数にして cache を効かせる。"""
    with zipfile.ZipFile(io.BytesIO(raw), "r") as z:
        with z.open("02_PropGeo.zip") as f:
            gdf_prop = gpd.read_file(f, encoding="utf-8")
        with z.open("03_Ring.zip") as f:
            gdf_ring = gpd.read_file(f, encoding="utf-8")
        with z.open("05_PostCode.csv") as f:
            df_postcode = pd.read_csv(f, encoding="utf-8", dtype={"PostCode": str})
        with z.open("06_MsbGeo.csv") as f:
            df_msb = pd.read_csv(f, encoding="utf-8", dtype=DTYPE_MSBGEO)
        with z.open("07_Stacking.csv") as f:
            df_stacking = pd.read_csv(f, encoding="utf-8", dtype=DTYPE_STACKING)
        with z.open("08_Sansan.csv") as f:
            df_sansan = pd.read_csv(f, encoding="utf-8", dtype=DTYPE_SANSAN)
        with z.open("09_Sansan_CBRE.csv") as f:
            df_cbre_div = pd.read_csv(f, encoding="utf-8")

    for df in (df_postcode, df_msb, df_sansan):
        df["PostCode"] = _norm_postcode(df["PostCode"])

    return {
        "prop": gdf_prop,
        "ring": gdf_ring,
        "postcode": df_postcode,
        "msb": df_msb,
        "stacking": df_stacking,
        "sansan": df_sansan,
        "cbre_div": df_cbre_div,
    }


def zoom_for_kilo(kilo: str) -> int:
    """'5km' のような文字列からズームレベルを決める。想定外の値でも落ちないようにする。"""
    try:
        km = float(str(kilo).lower().replace("km", "").strip())
    except ValueError:
        return 11
    if km <= 3:
        return 13
    if km <= 5:
        return 12
    if km <= 15:
        return 11
    return 10


# ==========================================================================
# 画面
# ==========================================================================

st.set_page_config(layout="wide", page_title="Tenant Radar APP")
st.title("Tenant Radar APP")

with st.sidebar:
    zip_capsule = st.file_uploader(label="Upload Capsule.zip", type="zip")

if zip_capsule is None:
    logo_path = APP_DIR / "ACube.PNG"
    if logo_path.exists():
        st.image(Image.open(logo_path), width=400)
    else:
        st.info("Capsule.zip をアップロードしてください。")
    st.stop()

data = load_capsule(zip_capsule.getvalue())

gdf_prop = data["prop"]
gdf_ring = data["ring"]
df_postcode = data["postcode"]
df_cbre_div = data["cbre_div"]

prop_lat = float(gdf_prop.loc[0, "POINT_Y"])
prop_lon = float(gdf_prop.loc[0, "POINT_X"])
prop_popup = "<br>".join(
    [gdf_prop.loc[0, "Label"], gdf_prop.loc[0, "Property"], gdf_prop.loc[0, "Address"]]
)


def add_subject_marker(m: fl.Map) -> None:
    grp = fl.FeatureGroup(name=gdf_prop.loc[0, "Label"], show=True).add_to(m)
    grp.add_child(
        fl.Marker(
            location=[prop_lat, prop_lon],
            popup=PU_START + prop_popup + PU_END,
            icon=BeautifyIcon(
                icon="star", border_width=2,
                border_color=BASE_COLOR[0], text_color=BASE_COLOR[0], spin=True,
            ),
        )
    )


# --------------------------------------------------------------------------
# サイドバー: リング選択 + 概観マップ
# --------------------------------------------------------------------------
with st.sidebar:
    kilo_values = list(gdf_ring.kilo.values)
    default_kilo = kilo_values[min(2, len(kilo_values) - 1)]
    kilo = st.select_slider("Ring Kilo :", kilo_values, default_kilo)

    small_map = new_map(prop_lat, prop_lon, zoom=8)
    add_subject_marker(small_map)
    st.components.v1.html(small_map.get_root().render(), height=300)

# --------------------------------------------------------------------------
# リングによる 1 次絞り込み（以降、この *_base を元データとして保持）
# --------------------------------------------------------------------------
postcode_list = df_postcode.loc[df_postcode.kilo == kilo, "PostCode"].tolist()

msb_base = data["msb"][data["msb"].PostCode.isin(postcode_list)].reset_index(drop=True)
stacking_base = data["stacking"][data["stacking"].kilo == kilo].reset_index(drop=True)
sansan_base = data["sansan"][data["sansan"].PostCode.isin(postcode_list)].reset_index(drop=True)

col1, col2, col3, _, _, _ = st.columns(6)
map_col, panel_col = st.columns(2)

# --------------------------------------------------------------------------
# 右ペイン: タブごとのフィルタ
# --------------------------------------------------------------------------
with panel_col:
    tab_sum, tab_stack, tab_sansan, tab_msb = st.tabs(
        ["Summary", "Stacking", "Sansan", "Musubu"]
    )

    # ---- Stacking ----
    with tab_stack:
        if stacking_base.empty:
            st.warning("このリングに Stacking データがありません。")
            area_min = area_max = 0.0
            grid_selected: list[str] = []
            stacking_f = stacking_base
        else:
            lo = float(stacking_base.Lease_Area.min())
            hi = float(stacking_base.Lease_Area.max())
            area_min = st.number_input("賃貸面積 From", min_value=lo, max_value=hi, value=lo)
            area_max = st.number_input("賃貸面積 To", min_value=lo, max_value=hi, value=hi)
            grid_selected = st.multiselect(
                label="GRID番号",
                options=stacking_base.GRID_BID.value_counts().index.tolist(),
                default=[],
            )
            mask = stacking_base.Lease_Area.between(area_min, area_max)
            if grid_selected:
                mask &= stacking_base.GRID_BID.isin(grid_selected)
            stacking_f = stacking_base[mask].reset_index(drop=True)

            st.dataframe(
                stacking_f[
                    ["CorpNum", "Comp_Name", "GRID_BID", "Property", "Address",
                     "Lease_Area", "CNT_Type", "CNT_Start", "CNT_End"]
                ].sort_values("Lease_Area", ascending=False),
                height=420,
                use_container_width=True,
            )

    # ---- Sansan ----
    with tab_sansan:
        cbre_div_selected = st.multiselect(
            label="CBRE Division",
            options=df_cbre_div.CBRE_Div.value_counts().index.tolist(),
            default=[],
        )
        sansan_f = sansan_base
        if cbre_div_selected:
            sansan_divs = df_cbre_div.loc[
                df_cbre_div.CBRE_Div.isin(cbre_div_selected), "Sansan_Div"
            ].unique()
            sansan_f = sansan_f[sansan_f.CBRE_Div.isin(sansan_divs)]

        sansan_pc_selected = st.multiselect(
            label="Sansan 郵便番号", options=postcode_list, default=[]
        )
        if sansan_pc_selected:
            sansan_f = sansan_f[sansan_f.PostCode.isin(sansan_pc_selected)]
        sansan_f = sansan_f.reset_index(drop=True)

        st.dataframe(
            sansan_f[
                ["CorpNum", "Comp_Name", "Div", "Title", "Address",
                 "CBRE_Div", "CBRE_Member", "PostCode"]
            ].sort_values("Comp_Name"),
            height=420,
            use_container_width=True,
        )

    # ---- Musubu ----
    with tab_msb:
        ind_selected = st.multiselect(
            label="メイン大業界",
            options=msb_base.Ind_Main1.value_counts().index.tolist(),
            default=[],
        )
        msb_f = msb_base
        if ind_selected:
            msb_f = msb_f[msb_f.Ind_Main1.isin(ind_selected)]

        msb_pc_selected = st.multiselect(
            label="Musubu 郵便番号", options=postcode_list, default=[]
        )
        if msb_pc_selected:
            msb_f = msb_f[msb_f.PostCode.isin(msb_pc_selected)]
        msb_f = msb_f.reset_index(drop=True)

        msb_cols = ["CorpNum", "Comp_Name", "Branch_Name", "Address",
                    "Tel", "Branch_1", "Ind_Main1", "PostCode"]
        msb_cols = [c for c in msb_cols if c in msb_f.columns]
        st.dataframe(
            msb_f[msb_cols].sort_values("Comp_Name"),
            height=420,
            use_container_width=True,
        )

    # ---- Summary（他タブのフィルタ結果を集計）----
    with tab_sum:
        sum_sort = st.radio(label="ソート", options=["Stacking", "Sansan", "Musubu"])
        df_sum = (
            pd.concat(
                [
                    msb_f.drop_duplicates(subset=["CorpNum", "Comp_Name"])[["CorpNum", "Comp_Name"]],
                    sansan_f.drop_duplicates(subset=["CorpNum", "Comp_Name"])[["CorpNum", "Comp_Name"]],
                    stacking_f.drop_duplicates(subset=["CorpNum", "Comp_Name"])[["CorpNum", "Comp_Name"]],
                ]
            )
            .drop_duplicates(subset="CorpNum")
            .set_index("CorpNum")
            .assign(
                Stacking=stacking_f.CorpNum.value_counts(),
                Sansan=sansan_f.CorpNum.value_counts(),
                Musubu=msb_f.CorpNum.value_counts(),
            )
            .fillna(0)
            .astype({"Stacking": int, "Sansan": int, "Musubu": int})
        )
        st.dataframe(
            df_sum.sort_values(sum_sort, ascending=False),
            height=420,
            use_container_width=True,
        )

# --------------------------------------------------------------------------
# メトリクス
# --------------------------------------------------------------------------
with col1:
    st.metric("Musubu 事業所数", len(msb_f))
with col2:
    st.metric("Stacking テナント数", len(stacking_f))
with col3:
    st.metric("Sansan 名刺数", len(sansan_f))

# --------------------------------------------------------------------------
# メインマップ
# --------------------------------------------------------------------------
main_map = new_map(prop_lat, prop_lon, zoom=zoom_for_kilo(kilo))
add_subject_marker(main_map)

# リング
grp = fl.FeatureGroup(name=f"{kilo}Ring", show=True).add_to(main_map)
grp.add_child(
    fl.GeoJson(
        data=gdf_ring[gdf_ring.kilo == kilo],
        style_function=lambda x: {
            "fillColor": BASE_COLOR[0], "color": BASE_COLOR[0],
            "weight": 2, "fillOpacity": 0.1,
        },
    )
)

# 郵便番号（value_counts で 1 パス集計）
msb_by_pc = msb_f.PostCode.value_counts().to_dict()
san_by_pc = sansan_f.PostCode.value_counts().to_dict()
pc_coords = df_postcode.drop_duplicates("PostCode").set_index("PostCode")

grp = fl.FeatureGroup(name=f"{kilo}Ring 郵便番号", show=True).add_to(main_map)
for pc in postcode_list:
    msb_n = msb_by_pc.get(pc, 0)
    san_n = san_by_pc.get(pc, 0)
    if msb_n + san_n == 0 or pc not in pc_coords.index:
        continue
    row = pc_coords.loc[pc]
    popup = "<br>".join([f"〒{pc}", f"Musubu : {msb_n}社", f"Sansan : {san_n}枚"])
    grp.add_child(
        fl.CircleMarker(
            location=[float(row.POINT_Y), float(row.POINT_X)],
            radius=2, weight=6, color="#fd8d3c",
            popup=PU_START + popup + PU_END,
        )
    )

# Stacking（groupby で 1 パス集計）
grp = fl.FeatureGroup(name=f"{kilo}Ring Stacking", show=True).add_to(main_map)
if not stacking_f.empty:
    grid_agg = stacking_f.groupby("GRID_BID").agg(
        POINT_X=("POINT_X", "first"),
        POINT_Y=("POINT_Y", "first"),
        Property=("Property", "first"),
        Comp_Num=("GRID_BID", "size"),
    )
    for grid_bid, row in grid_agg.iterrows():
        popup = "<br>".join([str(grid_bid), str(row.Property), f"{int(row.Comp_Num)}社"])
        grp.add_child(
            fl.CircleMarker(
                location=[float(row.POINT_Y), float(row.POINT_X)],
                radius=2, weight=6, color="#74c476",
                popup=PU_START + popup + PU_END,
            )
        )

fl.LayerControl().add_to(main_map)

# render は 1 回だけ（表示とダウンロードで使い回す）
main_map_html = main_map.get_root().render()

with map_col:
    st.components.v1.html(main_map_html, height=650)

# --------------------------------------------------------------------------
# サイドバー: 条件サマリ + ダウンロード
# --------------------------------------------------------------------------
with st.sidebar:
    st.subheader(f"Stacking : {area_min} 坪 ~ {area_max} 坪")
    st.subheader(
        "Sansan : " + (", ".join(cbre_div_selected) if cbre_div_selected else "All CBRE Divisions")
    )
    st.subheader(
        "Musubu : " + (", ".join(ind_selected) if ind_selected else "全業界")
    )

    st.download_button("🗺️ Map Download", main_map_html, file_name="Map.html")
    # df_sum は CorpNum が index のため index=True（元コードは index=False で法人番号が欠落していた）
    st.download_button(
        "📋 Download Summary csv",
        df_sum.to_csv(index=True).encode("utf-8-sig"),
        file_name="Summary.csv",
    )
    st.download_button(
        "📋 Download Musubu csv",
        msb_f.to_csv(index=False).encode("utf-8-sig"),
        file_name="Musubu.csv",
    )
    st.download_button(
        "📋 Download Stacking csv",
        stacking_f.to_csv(index=False).encode("utf-8-sig"),
        file_name="Stacking.csv",
    )
    st.download_button(
        "📋 Download Sansan csv",
        sansan_f.to_csv(index=False).encode("utf-8-sig"),
        file_name="Sansan.csv",
    )
