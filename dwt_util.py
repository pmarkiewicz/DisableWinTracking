# Copyright (C) 10se1ucgo 2015-2016
#
# This file is part of DisableWinTracking.
#
# DisableWinTracking is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# DisableWinTracking is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with DisableWinTracking.  If not, see <http://www.gnu.org/licenses/>.
import logging
import os
import platform
import pywintypes
import shutil
import subprocess
import tempfile
import win32serviceutil
import winerror
import winreg
import shlex

logger = logging.getLogger('dwt.util')


def is_64bit():
    # Detect if OS is 64bit
    return True if "64" in platform.uname().machine else False


def ip_block(ip_list, undo):
    for ip in ip_list:
        cmd = 'netsh advfirewall firewall {act} rule name="TrackingIP-{ip}"'.format(act='delete' if undo else 'add',
                                                                                    ip=ip)
        if not undo:
            cmd += ' dir=out protocol=any remoteip="{ip}" profile=any action=block'.format(ip=ip)

        try:
            subprocess_handler(shlex.split(cmd))
            logger.info("IP Blocker: The IP {ip} was successfully blocked.".format(ip=ip))
        except subprocess.CalledProcessError as e:
            logger.exception("IP Blocker: Failed to block IP {ip}".format(ip=ip))
            logger.critical("IP Blocker: Error output:\n" + e.stdout.decode('ascii', 'replace'))


def clear_diagtrack():
    file = os.path.join(os.environ['SYSTEMDRIVE'], ('/ProgramData/Microsoft/Diagnosis/ETLLogs/AutoLogger/'
                                                    'AutoLogger-Diagtrack-Listener.etl'))
    own_cmd = "takeown /f {file} && icacls {file} /grant administrators:F".format(file=file)
    lock_cmd = "echo y|cacls {file} /d SYSTEM".format(file=file)

    try:
        subprocess_handler(shlex.split(own_cmd))
    except subprocess.CalledProcessError as e:
        logger.exception("DiagTrack: Failed to clear DiagTrack log -- could not take ownership of file")
        logger.critical("DiagTrack: Error output:\n" + e.output.decode('ascii', 'replace'))
        return

    try:
        open(file, 'w').close()
        subprocess_handler(shlex.split(lock_cmd))
        logger.info("DiagTrack: Successfully cleared and locked DiagTrack log.")
    except subprocess.CalledProcessError as e:
        logger.exception("DiagTrack: Failed to clear DiagTrack log -- could not clear or lock")
        logger.critical("DiagTrack: Error output:\n" + e.output.decode('ascii', 'replace'))


def delete_service(service):
    try:
        win32serviceutil.RemoveService(service)
        logging.info("Services: Succesfully removed service '{service}'".format(service=service))
    except pywintypes.error as e:
        errors = (winerror.ERROR_SERVICE_DOES_NOT_EXIST, winerror.ERROR_SERVICE_NOT_ACTIVE)
        if not any(error == e.winerror for error in errors):
            logging.exception("Services: Failed to remove service '{service}'".format(service=service))


def disable_service(service):
    try:
        win32serviceutil.StopService(service)
        logging.info("Services: Succesfully stopped service '{service}'".format(service=service))
    except pywintypes.error as e:
        errors = (winerror.ERROR_SERVICE_DOES_NOT_EXIST, winerror.ERROR_SERVICE_NOT_ACTIVE)
        if not any(error == e.winerror for error in errors):
            logging.exception("Services: Failed to stop service '{service}'".format(service=service))


def telemetry(undo):
    value = int(undo)
    telemetry_keys = {'AllowTelemetry': [winreg.HKEY_LOCAL_MACHINE,
                                         r'SOFTWARE\Policies\Microsoft\Windows\DataCollection',
                                         "AllowTelemetry", winreg.REG_DWORD, value]}
    set_registry(telemetry_keys)


def services(undo):
    value = 4 if undo else 3
    service_keys = {'dmwappushsvc': [winreg.HKEY_LOCAL_MACHINE,
                                     r'SYSTEM\\CurrentControlSet\\Services\\dmwappushsvc',
                                     'Start', winreg.REG_DWORD, value],

                    'DiagTrack': [winreg.HKEY_LOCAL_MACHINE,
                                  r'SYSTEM\\CurrentControlSet\\Services\\DiagTrack',
                                  'Start', winreg.REG_DWORD, value]}
    set_registry(service_keys)


def defender(undo):
    value = int(undo)
    defender_keys = {'Windows Defender Delivery Optimization Download':
                     [winreg.HKEY_LOCAL_MACHINE,
                      r'SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config',
                      'DODownloadMode', winreg.REG_DWORD, value],

                     'Windows Defender Spynet': [winreg.HKEY_LOCAL_MACHINE,
                                                 r'SOFTWARE\Microsoft\Windows Defender\Spynet',
                                                 'SpyNetReporting', winreg.REG_DWORD, value],

                     'Windows Defender Sample Submission': [winreg.HKEY_LOCAL_MACHINE,
                                                            r'SOFTWARE\Microsoft\Windows Defender\Spynet',
                                                            'SubmitSamplesConsent', winreg.REG_DWORD, value]}
    set_registry(defender_keys)


def wifisense(undo):
    value = int(undo)
    wifisense_keys = {'WifiSense Credential Share': [winreg.HKEY_LOCAL_MACHINE,
                                                     r'SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\features',
                                                     'WiFiSenseCredShared', winreg.REG_DWORD, value],

                      'WifiSense Open-ness': [winreg.HKEY_LOCAL_MACHINE,
                                              r'SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\features',
                                              'WiFiSenseOpen', winreg.REG_DWORD, value]}
    set_registry(wifisense_keys)


def onedrive(undo):
    file_sync_value = int(undo)
    list_pin_value = int(not undo)
    action = "install" if undo else "uninstall"
    onedrive_keys = {'FileSync': [winreg.HKEY_LOCAL_MACHINE,
                                  r'SOFTWARE\Policies\Microsoft\Windows\OneDrive',
                                  'DisableFileSyncNGSC', winreg.REG_DWORD, file_sync_value],

                     'ListPin': [winreg.HKEY_CLASSES_ROOT,
                                 r'CLSID\{018D5C66-4533-4307-9B53-224DE2ED1FE6}',
                                 'System.IsPinnedToNameSpaceTree', winreg.REG_DWORD, list_pin_value]}

    set_registry(onedrive_keys)

    system = "SysWOW64" if is_64bit() else "System32"
    onedrive_setup = os.path.join(os.environ['SYSTEMROOT'], "{system}/OneDriveSetup.exe".format(system=system))
    cmd = "{bin} /{action}".format(bin=onedrive_setup, action=action)
    try:
        subprocess.call(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        logger.info("OneDrive: successfully {action}ed".format(action=action))
    except (WindowsError, IOError):
        logger.info("OneDrive: unable to {action}".format(action=action))


def set_registry(keys):
    mask = winreg.KEY_WOW64_64KEY | winreg.KEY_ALL_ACCESS if is_64bit() else winreg.KEY_ALL_ACCESS

    for key_name, values in keys.items():
        try:
            key = winreg.CreateKeyEx(values[0], values[1], 0, mask)
            winreg.SetValueEx(key, values[2], 0, values[3], values[4])
            winreg.CloseKey(key)
            logging.info("Registry: Successfully modified {key} key.".format(key=key_name))
        except OSError:
            logging.exception("Registry: Unable to mody {key} key.".format(key=key_name))


def host_file(entries, undo):
    null_ip = "0.0.0.0 "
    nulled_entires = [null_ip + x for x in entries]
    hosts_path = os.path.join(os.environ['SYSTEMROOT'], 'System32/drivers/etc/hosts')

    if undo:
        try:
            with open(hosts_path, 'r') as hosts, tempfile.NamedTemporaryFile(delete=False) as temp:
                for line in hosts:
                    if not any(domain in line for domain in entries):
                        temp.write(line)
                temp.close()
                shutil.move(temp.name, hosts_path)
            return True
        except OSError:
            logging.exception("Hosts: Failed to undo hosts file")
    else:
        try:
            with open(hosts_path, 'a') as f:
                f.write('\n' + '\n'.join(nulled_entires))
            return True
        except (WindowsError, IOError):
            logging.exception("Hosts: Failed to modify hosts file")

    return False


def app_manager(apps, undo):
    running = []
    for app in apps:
        cmd = 'powershell "Get-AppxPackage *{app}*|Remove-AppxPackage"'.format(app=app)
        try:
            process = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       stdin=subprocess.PIPE)
            running.append(process)
        except OSError:
            logging.exception("App remover: Failed to remove app '{app}'".format(app=app))

    for process in running:
        process.wait()


def subprocess_handler(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    output = p.communicate()
    if p.returncode:
        raise subprocess.CalledProcessError(returncode=p.returncode, cmd=cmd, output=output[0], stderr=output[1])

# Old reinstall code:
# if reinstall:
#     # We encode in Base64 because the command is complex and I'm too lazy to escape everything.
#     # It's uncoded format command: "Get-AppxPackage -AllUsers| Foreach {Add-AppxPackage -DisableDevelopmentMode
#     # -Register "$($_.InstallLocation)\AppXManifest.xml"}"
#     encodedcommand = 'Get-AppxPackage -AllUsers | Foreach {Add-AppxPackage -DisableDevelopmentMode # -Register \
#                      "$($_.InstallLocation)\AppXManifest.xml"}'
#     try:
#         subprocess.call("powershell -EncodedCommand {0}".format(encodedcommand), shell=True)
#     except (WindowsError, IOError):
#         print "App management: Could not re-install all apps"