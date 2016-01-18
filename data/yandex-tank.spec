Name:       yandex-tank
Version:    1.5.0
Release:    1%{?dist}
Summary:    Yandex.Tank (Load Testing Tool)

License:    MIT
URL:        https://github.com/yandex-load/yandex-tank
Source0:    %{name}-%{version}.tar.gz

BuildArch:  noarch
BuildRoot:  %(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

Requires:   python-psutil
Requires:   python-ipaddr


%description
Yandex.Tank is an extendable open source load testing tool for advanced linux users which is especially good as a part of automated load testing suit.

%prep
%setup -q

%build

%install
rm -rf %{buildroot}
mkdir -p  %{buildroot}
mkdir -p %{buildroot}/%{_bindir}
mkdir -p %{buildroot}/%{_sysconfdir}/yandex-tank/
mkdir -p %{buildroot}/%{_sysconfdir}/bash_completion.d/
mkdir -p %{buildroot}/%{_libdir}/yandex-tank/
cp -ap 00-base.ini %{buildroot}/%{_sysconfdir}/yandex-tank/
cp -ap yandex-tank.completion %{buildroot}/%{_sysconfdir}/bash_completion.d/
cp -arp Tank %{buildroot}/%{_libdir}/yandex-tank/
cp -ap tankcore.py %{buildroot}/%{_libdir}/yandex-tank/
cp -ap tank.py %{buildroot}/%{_libdir}/yandex-tank/
cp -ap *.sh %{buildroot}/%{_libdir}/yandex-tank/
ln -s %{_libdir}/yandex-tank/tank.py %{buildroot}/%{_bindir}/yandex-tank

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{_sysconfdir}/yandex-tank
%{_sysconfdir}/bash_completion.d/yandex-tank.completion
%{_bindir}/lunapark
%{_bindir}/yandex-tank
%{_libdir}/yandex-tank

%changelog
* Wed Mar 19 2014  Andrey Pohilko (undera) <undera@yandex-team.ru> - 1.5.0
- Static HTML report with Highcharts graphs: tank metrics and monitoring
- Highcharts template for Graphite reports
- Better hostname resolve method
- Bugfixes
- collect 'cached' mem by default
- fix collecting disk activity on lxc containers
- add steady_cumulative autostop criteria
- don't fail test on agent shutdown problems
- fix rcheck on remote fs
