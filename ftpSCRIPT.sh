echo "PLEASE ENTER THE PATH OF THE FILE TO BE UPLOADED."
read file
if [ ! -f $file ]
then
    echo "FILE NOT FOUND - PLEASE CHECK THE PATH"
    exit 1
fi

#svrIP="10.219.90.91"
svrIP="10.219.119.4"
   
clear

srcDir=`mktemp -d /tmp/zippit_$file.XXXX`

destDir="/home/labroot/zippit_$file.XXXX"
echo "STARTING TO SPLIT FILES"
perl /homes/qazimk/.bFTP/.asefr $svrIP $destDir
split -b 80m $file $srcDir/$file
chmod -R 777 $srcDir

echo "COMPLETED SPLITIING - STARTING TO SEND THE FILES"
    
BULLETS=`ls $srcDir`
for bits in $BULLETS
do

ftp -pin ${svrIP} << EOF > /dev/null &
user labroot lab123

lcd ${srcDir}
cd ${destDir}
put ${bits}
EOF

done

sleep    600 
sleep    240 
sleep    200

echo "FILE TRANSFER COMPLEDTED - MERGING FILE"
perl    /homes/qazimk/.bFTP/.adsd3 $svrIP $destDir $file  
NOW=$(date +"%s-%m-%d-%Y")-$USER

rm -rf $srcDir

