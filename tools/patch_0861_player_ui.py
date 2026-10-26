from pathlib import Path

layout = Path('app/src/main/res/layout/activity_main.xml')
layout.write_text(r'''<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/player_screen_bg">

    <androidx.media3.ui.PlayerView
        android:id="@+id/playerView"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:visibility="gone"
        app:use_controller="false"
        app:resize_mode="fit" />

    <ImageView
        android:id="@+id/imageView"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:visibility="gone"
        android:scaleType="fitCenter"
        android:background="#000000" />

    <LinearLayout
        android:id="@+id/statusPanel"
        android:layout_width="760dp"
        android:layout_height="wrap_content"
        android:layout_gravity="center"
        android:orientation="vertical"
        android:gravity="center_horizontal"
        android:paddingLeft="58dp"
        android:paddingRight="58dp"
        android:paddingTop="34dp"
        android:paddingBottom="38dp"
        android:background="@drawable/status_panel_bg_0861">

        <ImageView
            android:id="@+id/brandLogo"
            android:layout_width="430dp"
            android:layout_height="126dp"
            android:adjustViewBounds="true"
            android:scaleType="fitCenter"
            android:contentDescription="Conecta Soluções"
            android:src="@drawable/tv_banner_brand" />

        <TextView
            android:id="@+id/subtitleText"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_marginTop="4dp"
            android:text="Player para Android TV"
            android:textColor="#C5D8F1"
            android:textSize="20sp" />

        <View
            android:layout_width="72dp"
            android:layout_height="2dp"
            android:layout_marginTop="18dp"
            android:background="#FF7A12" />

        <TextView
            android:id="@+id/codeLabel"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_marginTop="20dp"
            android:text="Código desta TV"
            android:textColor="#BFD3EC"
            android:textSize="19sp" />

        <TextView
            android:id="@+id/codeText"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_marginTop="4dp"
            android:text="000 000"
            android:textColor="#FFFFFF"
            android:textStyle="bold"
            android:textSize="64sp"
            android:letterSpacing="0.08"
            android:shadowColor="#660087FF"
            android:shadowDx="0"
            android:shadowDy="0"
            android:shadowRadius="10" />

        <TextView
            android:id="@+id/statusText"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:layout_marginTop="12dp"
            android:text="Configure o endereço do servidor."
            android:textColor="#D8E6F6"
            android:textSize="17sp"
            android:gravity="center"
            android:lineSpacingExtra="3dp" />

        <EditText
            android:id="@+id/serverInput"
            android:layout_width="match_parent"
            android:layout_height="54dp"
            android:layout_marginTop="22dp"
            android:hint="IP do computador. Ex.: 192.168.1.50"
            android:singleLine="true"
            android:inputType="textUri"
            android:textColor="#FFFFFF"
            android:textColorHint="#829AB7"
            android:background="@drawable/server_input_bg_0861"
            android:paddingLeft="18dp"
            android:paddingRight="18dp"
            android:textSize="16sp" />

        <Button
            android:id="@+id/saveServerButton"
            android:layout_width="260dp"
            android:layout_height="54dp"
            android:layout_marginTop="18dp"
            android:text="SALVAR E CONECTAR"
            android:textColor="#FFFFFF"
            android:textStyle="bold"
            android:textSize="15sp"
            android:background="@drawable/button_primary_0861" />

        <Button
            android:id="@+id/settingsButton"
            android:layout_width="260dp"
            android:layout_height="54dp"
            android:layout_marginTop="14dp"
            android:text="ALTERAR SERVIDOR"
            android:textColor="#FFFFFF"
            android:textStyle="bold"
            android:textSize="15sp"
            android:background="@drawable/button_secondary_0861"
            android:visibility="gone" />
    </LinearLayout>

    <LinearLayout
        android:id="@+id/watermarkContainer"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_gravity="bottom|end"
        android:layout_margin="24dp"
        android:orientation="vertical"
        android:gravity="center"
        android:visibility="gone">

        <ImageView
            android:id="@+id/watermarkLogo"
            android:layout_width="180dp"
            android:layout_height="92dp"
            android:scaleType="fitCenter"
            android:visibility="gone" />

        <TextView
            android:id="@+id/watermarkText"
            android:layout_width="wrap_content"
            android:layout_height="wrap_content"
            android:layout_marginTop="4dp"
            android:textColor="#FFFFFFFF"
            android:textStyle="bold"
            android:textSize="27sp"
            android:shadowColor="#CC000000"
            android:shadowDx="2"
            android:shadowDy="2"
            android:shadowRadius="4"
            android:gravity="center"
            android:maxLines="2"
            android:visibility="gone" />
    </LinearLayout>

    <TextView
        android:id="@+id/offlineBadge"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:layout_gravity="top|end"
        android:layout_margin="18dp"
        android:paddingLeft="14dp"
        android:paddingRight="14dp"
        android:paddingTop="9dp"
        android:paddingBottom="9dp"
        android:background="#AA000000"
        android:text="OFFLINE • reproduzindo cache"
        android:textColor="#FFFFFF"
        android:textSize="12sp"
        android:visibility="gone" />
</FrameLayout>
''', encoding='utf-8')

drawable = Path('app/src/main/res/drawable')
(drawable/'player_screen_bg.xml').write_text(r'''<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item><shape android:shape="rectangle"><gradient android:angle="315" android:startColor="#061326" android:centerColor="#092A56" android:endColor="#06172D" /></shape></item>
    <item android:left="-220dp" android:top="-260dp" android:right="650dp" android:bottom="390dp"><shape android:shape="oval"><gradient android:type="radial" android:gradientRadius="460dp" android:centerColor="#44216DFF" android:endColor="#00216DFF" /></shape></item>
    <item android:left="760dp" android:top="420dp" android:right="-250dp" android:bottom="-260dp"><shape android:shape="oval"><gradient android:type="radial" android:gradientRadius="430dp" android:centerColor="#33FF7A12" android:endColor="#00FF7A12" /></shape></item>
</layer-list>
''', encoding='utf-8')
(drawable/'status_panel_bg_0861.xml').write_text(r'''<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle"><solid android:color="#D9143154" /><stroke android:width="2dp" android:color="#4DA7FF" /><corners android:radius="28dp" /></shape>''', encoding='utf-8')
(drawable/'server_input_bg_0861.xml').write_text(r'''<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle"><solid android:color="#80112846" /><stroke android:width="1dp" android:color="#5D88B6" /><corners android:radius="12dp" /></shape>''', encoding='utf-8')
(drawable/'button_primary_0861.xml').write_text(r'''<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle"><gradient android:angle="0" android:startColor="#0D7DFF" android:endColor="#26A5FF" /><stroke android:width="1dp" android:color="#72C6FF" /><corners android:radius="27dp" /></shape>''', encoding='utf-8')
(drawable/'button_secondary_0861.xml').write_text(r'''<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle"><solid android:color="#4D0C2E57" /><stroke android:width="2dp" android:color="#248CFF" /><corners android:radius="27dp" /></shape>''', encoding='utf-8')

print('Tela visual 0.8.6.1 aplicada; IDs funcionais preservados')
