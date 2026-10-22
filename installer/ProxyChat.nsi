!include "MUI2.nsh"
!include "FileFunc.nsh"

; Surum build_installer.ps1 tarafindan /DAPP_VERSION ile gecirilir;
; tek kaynak apps/proxychat/version.py icindeki APP_VERSION sabitidir.
!ifndef APP_VERSION
  !define APP_VERSION "0.0.0"
!endif

!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProxyChat"

; Paketlenen dosyanin degistirilme zamani kuruluma YAZILMASIN. Varsayilan
; (SetDateSave on) exe'nin mtime'ini gomuyordu: icerigi ayni exe'yi baska bir
; klasorde ya da makinede derleyen biri farkli bir Setup ozeti aliyordu, yani
; kurulum yalnizca ayni klasorde yeniden uretilebilirdi. Olculdu (2026-10-22):
; yalnizca mtime'i esitlemek ozeti birebir tutturdu.
SetDateSave off

Name "ProxyChat"
OutFile "..\dist\ProxyChat-Setup.exe"

; KULLANICI-BAZLI KURULUM.
;
; Eskiden burada RequestExecutionLevel admin ve $PROGRAMFILES64 vardi. Bu
; kurulumun yonetici olarak yukseltilmesine yol aciyordu ve NSIS'te $DESKTOP,
; $SMPROGRAMS ve HKCU "kurulumu calistiran hesabi" gosterdigi icin, ayri bir
; yonetici hesabi olan makinelerde kisayollar ve kaldirma kaydi o hesabin
; profiline yaziliyordu: sihirbaz basariyla bitiyor ama kullanici masaustunde,
; baslat menusunde ve "Uygulamalar ve ozellikler" listesinde hicbir sey
; gormuyordu. Kullanici-bazli kurulumda yukseltme hic olmadigi icin bu
; uyusmazlik ortadan kalkiyor ve arkadaslara gonderirken UAC de sorulmuyor.
InstallDir "$LOCALAPPDATA\Programs\ProxyChat"
InstallDirRegKey HKCU "Software\ProxyChat" "InstallDir"
RequestExecutionLevel user

ShowInstDetails show
ShowUninstDetails show
Icon "..\assets\ProxyChat.ico"
UninstallIcon "..\assets\ProxyChat.ico"

!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\ProxyChat.ico"
!define MUI_UNICON "..\assets\ProxyChat.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

; Son sayfada "Run ProxyChat" kutusu varsayilan olarak isaretli gelir;
; isaret kaldirilirsa program acilmaz. Kurulum yukseltilmedigi icin
; (RequestExecutionLevel user) program yonetici olarak acilmaz. Sessiz
; kurulumda (/S) son sayfa gosterilmedigi icin program acilmaz.
!define MUI_FINISHPAGE_RUN "$INSTDIR\ProxyChat.exe"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "ProxyChat" SecMain
    ; Kisayollar ve kayitlar acikca oturum acmis kullanicinin profiline.
    SetShellVarContext current

    SetOutPath "$INSTDIR"
    File "..\dist\ProxyChat.exe"

    WriteUninstaller "$INSTDIR\Uninstall.exe"

    CreateDirectory "$SMPROGRAMS\ProxyChat"
    CreateShortcut "$SMPROGRAMS\ProxyChat\ProxyChat.lnk" "$INSTDIR\ProxyChat.exe"
    CreateShortcut "$DESKTOP\ProxyChat.lnk" "$INSTDIR\ProxyChat.exe"

    WriteRegStr HKCU "Software\ProxyChat" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "ProxyChat"
    WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" '"$INSTDIR\ProxyChat.exe"'
    WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
    WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1

    ; "Uygulamalar ve ozellikler" ekraninda boyut gorunsun.
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKCU "${UNINST_KEY}" "EstimatedSize" "$0"
SectionEnd

Section "Uninstall"
    SetShellVarContext current

    Delete "$DESKTOP\ProxyChat.lnk"
    Delete "$SMPROGRAMS\ProxyChat\ProxyChat.lnk"
    RMDir "$SMPROGRAMS\ProxyChat"

    Delete "$INSTDIR\ProxyChat.exe"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"

    ; Log dosyalari da birakilmaz.
    Delete "$LOCALAPPDATA\ProxyChat\logs\proxychat.log"
    Delete "$LOCALAPPDATA\ProxyChat\logs\proxychat.log.1"
    RMDir "$LOCALAPPDATA\ProxyChat\logs"
    RMDir "$LOCALAPPDATA\ProxyChat"

    ; Saklanan baglanti ayarlari ve (varsa) DPAPI ile sifrelenmis oda parolasi
    ; makinede birakilmaz.
    DeleteRegKey HKCU "Software\ProxyNet\ProxyChat"
    DeleteRegKey /ifempty HKCU "Software\ProxyNet"

    DeleteRegKey HKCU "${UNINST_KEY}"
    DeleteRegKey HKCU "Software\ProxyChat"
SectionEnd
