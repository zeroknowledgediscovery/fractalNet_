import cynet_utils.spatial as sp
import pandas as pd
from tqdm import tqdm

class Performance(object):
    """ """

    def __init__(self,
                 simfile,
                 RUNLEN,
                 FLEX_TAIL_LEN,
                 VERBOSE=False):
        """Performance evaluation for cynet runs. This is currently tuned for urban crime.
        Make sure the simulation csv has the *actual_count* column in it. The following shows
        example usage. 
        ```
           import cynet_utils.performance as pp
           P=pp.Performance('sim.csv',RUNLEN=639,FLEX_TAIL_LEN=30)
           P.getPaiPae(var='MOTOR_VEHICLE_THEFT',TIMERANGE_OF_PERFORMANCE=2)
           P.getPaiPae(var='STREET_CRIMES',TIMERANGE_OF_PERFORMANCE=2)
           P.getPaiPae(var=None,TIMERANGE_OF_PERFORMANCE=2)
        ```
        Version:
          0.0.1

        Args:
          simfile (str): simualtion csv with predictions, events and actual_count. 
                         Columns in the csv need to be:

                            day,lat1,lat2,lon1,lon2,target,actual_event,negative_event,positive_event,predictions,source,threshold,actual_count
                         
          RUNLEN (int): length of run as defined in main cynet workflow 
          FLEX_TAIL_LEN (int): tail length as defined in main cynet workflow 
          VERBOSE (bool): if True print status (Default value = False)

        Returns:

        """
        self.simfile = simfile
        self.RUNLEN = RUNLEN
        self.FLEX_TAIL_LEN = FLEX_TAIL_LEN

        self.VERBOSE = VERBOSE
        self.day_min=None
        self.TOTAL_AREA=None
        self.DFTP={}
        self.DFG={}
        self.DPP={}
        self.FP={}
        self.lat_min=None
        self.lat_max = None
        self.lon_min=None
        self.lon_max=None
        self.day_min = self.RUNLEN-self.FLEX_TAIL_LEN
        self.simdf = pd.read_csv(self.simfile)
        self.simdf = self.simdf[ (
            self.simdf['day'] >= self.day_min) & (
                self.simdf['target'] != 'VAR') ]
        self.TOTAL_AREA=len(list(
            set(self.simdf.set_index(
                ['lat1','lat2','lon1','lon2']).index)))
        self.lat_min = self.simdf.lat1.min()
        self.lat_max = self.simdf.lat2.max()
        self.lon_min = self.simdf.lon1.min()
        self.lon_max = self.simdf.lon2.max()

        
    def __mklist__(self,var=None):
        if var is None:
            var = self.simdf.target.unique()
        if isinstance(var,str):
            var=[var]

        return var

        
    def getPredictionDicts(self,var=None,D=0.5,Z=0.06):
        """Generate dictionaries for evaluating performance

        Args:
          var (list[str]): list of target variables on which performance is evaluated. 
                           For None we use all variables (Default value = None)
          D (float): relaxation parameter (Default value = 0.5)
          Z (float): relaxation parameter (Default value = 0.06)

        Returns:

        """
        
        var=self.__mklist__(var)
        var_='#'.join(var)
        self.DFTP[var_]={}
        self.DFG[var_]={}
        self.FP[var_]=0
        self.DPP[var_]={}

        for day in tqdm(range(self.day_min, self.RUNLEN)):
            _,_,fp,_,_,_,_,_,_,dfG,_,dfTP,dfFP,_,pred_ = sp.get_prediction(
                self.simdf,
                day,
                var,
                self.lat_min,
                self.lat_max,
                self.lon_min,
                self.lon_max,
                radius=8,
                sigma=3.5,
                detail=1.2,
                miles=D,
                Z=Z,RETURN_PRED=True)
            self.DFTP[var_][day]=dfTP
            self.DFG[var_][day]=dfG
            self.DPP[var_][day]=pred_
            self.FP[var_]=self.FP[var_]+fp
        return 

    
    def __union_dict__(self,D,KEYS):
        """Utility for customized unions of event dataframes

        Args:
          D (dict[int,pandas.DataFrame()]) : Union target
          KEYS list[int]: list fo timeunits on which to carry out union operation

        Returns:

        """
        
        xf=pd.concat([D[key][['lat1','lat2','lon1',
                              'lon2',
                              'actual_count']].set_index(['lat1',
                                                          'lat2','lon1','lon2'])
                      for key in KEYS])
        return xf.reset_index().groupby(['lat1','lat2','lon1','lon2']).sum()


    def __getPAE__(self,dtp,dg,dp,KEYS):
        """Internal logic for PAI PEI calculation

        Args:
          dtp (pandas.DataFrame): TP
          dg (pandas.DataFrame): dataframe of ground truth. slice of sim.csv with `actual_event==1`
          dp (pandas.DataFrame): dataframe of predictions. Slice of sim.csv where `predictions==1`
          KEYS (list[int]): List of timeunits in target oos period 

        Returns:

        """
        
        nn0=dtp.join(
            dg,lsuffix='_tp',rsuffix='_gnd').dropna().index.size
        nstar=dg.sort_values(
            'actual_count').tail(nn0).actual_count.sum()
        #a=dtp.join(
        #    dg,lsuffix='_tp',rsuffix='_gnd').drop_duplicates().index.size
        a=dp.drop_duplicates().index.size
        N=dg.sort_values(
            'actual_count').actual_count.sum()
        n=dtp.join(
            dg,lsuffix='_tp',rsuffix='_gnd').dropna().actual_count_gnd.sum()
        return (n*self.TOTAL_AREA)/(N*a),n/nstar


    def getPaiPae(self,var,TIMERANGE_OF_PERFORMANCE,VERBOSE=True):
        """Calculate PAI and PEI

        Args:
          TIMERANGE_OF_PERFORMANCE (int): Number of time units in teh oos period 
                                          over which PAI andf PEI is calculated
          VERBOSE (bool):  (Default value = True)

        Returns:

        """
        
        var=self.__mklist__(var)
        var_='#'.join(var)
        if var_ not in self.DFTP.keys():
            self.getPredictionDicts(var)
        
        KEYS=[x for x in range(
            self.day_min,self.day_min+TIMERANGE_OF_PERFORMANCE)]    
        dtp=self.__union_dict__(self.DFTP[var_],KEYS)
        dg=self.__union_dict__(self.DFG[var_],KEYS)
        dp=self.__union_dict__(self.DPP[var_],KEYS)
        PAI,PEI=self.__getPAE__(dtp,dg,dp,KEYS)
        if self.VERBOSE:
            print('TIMERANGE',
                  TIMERANGE_OF_PERFORMANCE,
                  'PAI',PAI,'PEI',PEI)
        return PAI,PEI


